"""Turn detections, behaviour events and sensor readings into LOW / MEDIUM / HIGH risk and a light response.

LOW    -> nobody around: light dimmed at night (low_brightness %), off by day, buzzer off
MEDIUM -> person/motion at night, a crowd, someone lingering, or several people running: light 100 %
HIGH   -> a weapon (or a crime class from a custom model) seen in at least 2 of the last 3 detection
          passes, or a sustained crime behaviour (possible fight, person down, hands raised near
          someone): light 100 %, buzzer on
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

from .behavior import Event
from .detection import Detection

LEVELS = ("LOW", "MEDIUM", "HIGH")
HIGH_HOLD_SECONDS = 8  # keep HIGH briefly after the weapon leaves frame, so the light/buzzer do not flicker
TRACK_FORGET_SECONDS = 4  # a tracked person missing this long has left
PRESENCE_GRACE_SECONDS = 3  # detections flicker; a gap shorter than this does not restart the lingering timer


@dataclass
class RiskResult:
    level: str = "LOW"
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    brightness: int = 0
    buzzer: bool = False
    weapon: Detection | None = None
    event: Event | None = None  # crime behaviour (or crime class from a custom model) behind a HIGH

    @property
    def threat_label(self) -> str | None:
        if self.weapon:
            return self.weapon.label.replace("_", " ")
        return self.event.label if self.event else None

    def as_dict(self) -> dict:
        return {
            "level": self.level, "score": self.score, "reasons": self.reasons,
            "brightness": self.brightness, "buzzer": self.buzzer,
            "weapon": self.weapon.as_dict() if self.weapon else None,
            "event": self.event.as_dict() if self.event else None,
            "threat": self.threat_label,
        }


class RiskEngine:
    def __init__(self) -> None:
        self._threat_passes: deque[bool] = deque(maxlen=3)
        self._last_threat: Detection | None = None
        self._cause: Detection | Event | None = None  # what is holding HIGH
        self._high_until = 0.0
        self._presence_since: float | None = None
        self._last_presence = 0.0
        self._tracks: dict[int, list[float]] = {}  # person track id -> [first seen, last seen]

    def reset(self) -> None:
        self.__init__()

    def evaluate(self, detections: list[Detection], *, is_night: bool, motion: bool, settings: dict,
                 events: list[Event] | None = None, now: float | None = None) -> RiskResult:
        now = now or time.time()
        events = events or []
        people = sum(d.category == "person" for d in detections)
        vehicles = sum(d.category == "vehicle" for d in detections)
        # weapons and crime classes from custom models need 2 of the last 3 passes (single frames flicker);
        # behaviour events arrive already sustained, so they count at once
        threats = [d for d in detections if d.category in ("weapon", "event")]
        self._threat_passes.append(bool(threats))
        if threats:
            self._last_threat = max(threats, key=lambda d: (d.category == "weapon", d.confidence))

        if people or motion:
            self._presence_since = self._presence_since or now
            self._last_presence = now
        elif now - self._last_presence > PRESENCE_GRACE_SECONDS:
            self._presence_since = None
        lingering = now - self._presence_since if self._presence_since else 0
        # With tracking, time each person separately: a busy street is not "someone lingering".
        tracked = [d.track_id for d in detections if d.category == "person" and d.track_id is not None]
        for track_id in tracked:
            self._tracks.setdefault(track_id, [now, now])[1] = now
        self._tracks = {k: v for k, v in self._tracks.items() if now - v[1] <= TRACK_FORGET_SECONDS}
        lingerer = None
        if tracked:
            lingerer = max(tracked, key=lambda k: now - self._tracks[k][0])
            lingering = now - self._tracks[lingerer][0]

        result = RiskResult()
        high_events = [e for e in events if e.severity == "HIGH"]
        if threats and sum(self._threat_passes) >= 2:
            self._high_until, self._cause = now + HIGH_HOLD_SECONDS, self._last_threat
        elif high_events:
            self._high_until, self._cause = now + HIGH_HOLD_SECONDS, max(high_events, key=lambda e: e.confidence)
        cause = self._cause if now <= self._high_until else None
        if cause is not None:
            result.level = "HIGH"
            if isinstance(cause, Detection) and cause.category == "weapon":
                result.weapon = cause
                result.reasons.append(f"{cause.label.replace('_', ' ').title()} detected ({cause.confidence:.0%} confidence)")
            elif isinstance(cause, Detection):
                result.event = Event("model", f"{cause.label.replace('_', ' ').title()} detected", "HIGH",
                                     box=cause.box, confidence=cause.confidence)
                result.reasons.append(f"{result.event.label} ({cause.confidence:.0%} confidence)")
            else:
                result.event = cause
                result.reasons.append(cause.label)
            result.score = min(100, 70 + round(30 * cause.confidence))
        else:
            self._cause = None
            if not threats:
                self._last_threat = None
            for event in events:
                if event.severity == "MEDIUM":
                    result.level = "MEDIUM"
                    result.reasons.append(event.label)
            if is_night and (people or motion):
                result.level = "MEDIUM"
                result.reasons.append("Person or motion detected at night" if people else "PIR motion at night")
            if people >= settings["crowd_threshold"]:
                result.level = "MEDIUM"
                result.reasons.append(f"Crowd of {people} people")
            if is_night and lingering >= settings["loiter_seconds"]:
                result.level = "MEDIUM"
                who = f"Person #{lingerer}" if lingerer is not None else "Someone"
                result.reasons.append(f"{who} lingering for {int(lingering)} s")
            if result.level == "MEDIUM":
                result.score = min(65, 40 + people * 4 + vehicles * 2 + (10 if lingering >= settings["loiter_seconds"] else 0))
            else:
                result.score = min(30, people * 5 + vehicles * 2)
                result.reasons.append("No threat detected" if (people or vehicles) else "Street clear")

        if result.level == "LOW":
            result.brightness = settings["low_brightness"] if is_night else 0
        else:
            result.brightness = 100
        result.buzzer = result.level == "HIGH"
        return result
