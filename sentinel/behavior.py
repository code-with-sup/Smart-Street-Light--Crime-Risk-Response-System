"""Crime-behaviour cues from tracked people and their body pose (COCO 17 keypoints).

These are transparent rules, not a trained crime classifier, so every event is labelled "possible"
and must persist for a moment before it counts:

  person_down  someone lying on the ground (fall or assault)             -> HIGH
  hands_up     both hands above the head with another person close by    -> HIGH   (possible robbery)
  fight        two people in contact with fast, repeated arm movement     -> HIGH
  running      two or more people running at the same time                -> MEDIUM (possible incident)

Distances and speeds are measured in body heights, so the rules work at any camera distance.
"""

from __future__ import annotations

from collections import deque
from itertools import pairwise
from dataclasses import dataclass, field

import numpy as np

from .detection import Detection

# COCO keypoint indices
NOSE, L_SHOULDER, R_SHOULDER, L_WRIST, R_WRIST, L_HIP, R_HIP = 0, 5, 6, 9, 10, 11, 12
KP_MIN_CONF = 0.4
HISTORY_SECONDS = 3.0
TRACK_TIMEOUT = 2.0

DOWN_SECONDS = 2.0          # lying down this long
HANDS_UP_SECONDS = 1.5      # hands above head this long
NEAR_HEIGHTS = 2.0          # "close by" = within two body heights
CONTACT_HEIGHTS = 0.9       # "in contact" = centres closer than ~one body height
FAST_ARM = 2.0              # wrist speed in body heights per second that counts as a strike
FIGHT_WINDOW = 1.5          # look back this far for strikes
FIGHT_STRIKES = 3           # fast-arm samples needed in the window
RUN_SPEED = 1.6             # body heights per second
RUN_SECONDS = 1.0


@dataclass
class Event:
    kind: str                       # person_down | hands_up | fight | running
    label: str
    severity: str                   # HIGH | MEDIUM
    track_ids: tuple = ()
    box: tuple | None = None        # union box of the people involved
    confidence: float = 0.6

    def as_dict(self) -> dict:
        return {"kind": self.kind, "label": self.label, "severity": self.severity,
                "track_ids": list(self.track_ids), "box": self.box, "confidence": round(self.confidence, 2)}


@dataclass
class _Sample:
    t: float
    box: tuple
    kps: np.ndarray | None
    cut_off: bool = False  # box touches the top or bottom of the frame: only part of the body is visible


@dataclass
class _Track:
    samples: deque = field(default_factory=lambda: deque(maxlen=60))
    last_seen: float = 0.0


def _height(box) -> float:
    return max(1.0, box[3] - box[1])


def _centre(box) -> np.ndarray:
    return np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2], dtype=float)


def _kp(kps, index):
    if kps is None or kps[index, 2] < KP_MIN_CONF:
        return None
    return kps[index, :2]


def _is_lying(sample: _Sample) -> bool:
    """Lying = the whole torso is visible and horizontal. A wide box alone is not enough: someone sitting
    close to the camera (head and shoulders only, cut off by the frame) also gives a wide box."""
    if sample.cut_off:
        return False
    torso_points = [_kp(sample.kps, i) for i in (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP)]
    if any(p is None for p in torso_points):
        return False
    shoulders = np.mean(torso_points[:2], axis=0)
    hips = np.mean(torso_points[2:], axis=0)
    torso = hips - shoulders
    length = float(np.linalg.norm(torso))
    if length < 0.15 * max(_height(sample.box), sample.box[2] - sample.box[0]):
        return False  # torso too short to judge (e.g. facing the camera, bent over)
    return abs(torso[0]) > 1.5 * abs(torso[1])


def _hands_up(sample: _Sample) -> bool:
    nose, lw, rw = _kp(sample.kps, NOSE), _kp(sample.kps, L_WRIST), _kp(sample.kps, R_WRIST)
    if nose is None or lw is None or rw is None:
        return False
    return lw[1] < nose[1] and rw[1] < nose[1]


def _union(boxes) -> tuple:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


class BehaviorAnalyzer:
    def __init__(self) -> None:
        self._tracks: dict[int, _Track] = {}

    def reset(self) -> None:
        self._tracks.clear()

    def update(self, detections: list[Detection], now: float, frame_size: tuple[int, int] | None = None) -> list[Event]:
        people = [d for d in detections if d.category == "person" and d.track_id is not None]
        frame_h = frame_size[1] if frame_size else None
        for d in people:
            track = self._tracks.setdefault(d.track_id, _Track())
            cut_off = bool(frame_h) and (d.box[1] <= 0.02 * frame_h or d.box[3] >= 0.98 * frame_h)
            track.samples.append(_Sample(now, d.box, d.keypoints, cut_off))
            track.last_seen = now
        for track_id in [k for k, t in self._tracks.items() if now - t.last_seen > TRACK_TIMEOUT]:
            del self._tracks[track_id]
        for track in self._tracks.values():
            while track.samples and now - track.samples[0].t > HISTORY_SECONDS:
                track.samples.popleft()

        visible = {d.track_id: d for d in people}
        events: list[Event] = []
        events += self._person_down(visible, now)
        events += self._hands_up(visible, now)
        events += self._fight(visible, now)
        events += self._running(visible, now)
        return events

    # ------------------------------------------------------------- rules
    def _recent(self, track_id: int, now: float, seconds: float) -> list[_Sample]:
        return [s for s in self._tracks[track_id].samples if now - s.t <= seconds]

    def _sustained(self, track_id: int, now: float, seconds: float, test) -> bool:
        samples = self._recent(track_id, now, seconds + 0.25)
        if len(samples) < 3 or now - samples[0].t < seconds * 0.9:
            return False
        return all(test(s) for s in samples)

    def _person_down(self, visible, now) -> list[Event]:
        return [Event("person_down", "Person down — possible fall or assault", "HIGH", (tid,), d.box, 0.65)
                for tid, d in visible.items() if self._sustained(tid, now, DOWN_SECONDS, _is_lying)]

    def _hands_up(self, visible, now) -> list[Event]:
        events = []
        for tid, d in visible.items():
            if not self._sustained(tid, now, HANDS_UP_SECONDS, _hands_up):
                continue
            h = _height(d.box)
            others = [o for oid, o in visible.items() if oid != tid
                      and np.linalg.norm(_centre(o.box) - _centre(d.box)) < NEAR_HEIGHTS * max(h, _height(o.box))]
            if others:
                ids = (tid, *(o.track_id for o in others))
                events.append(Event("hands_up", "Hands raised near another person — possible robbery", "HIGH",
                                    ids, _union([d.box, *(o.box for o in others)]), 0.6))
        return events

    def _strikes(self, track_id: int, now: float) -> int:
        """Number of samples in the window where a wrist moved faster than FAST_ARM body heights/s."""
        samples = self._recent(track_id, now, FIGHT_WINDOW)
        count = 0
        for prev, cur in pairwise(samples):
            dt = cur.t - prev.t
            if dt <= 0:
                continue
            h = _height(cur.box)
            for wrist in (L_WRIST, R_WRIST):
                a, b = _kp(prev.kps, wrist), _kp(cur.kps, wrist)
                if a is not None and b is not None and np.linalg.norm(b - a) / h / dt > FAST_ARM:
                    count += 1
                    break
        return count

    def _fight(self, visible, now) -> list[Event]:
        events, ids = [], sorted(visible)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                da, db = visible[a], visible[b]
                close = np.linalg.norm(_centre(da.box) - _centre(db.box)) < CONTACT_HEIGHTS * max(_height(da.box), _height(db.box))
                if close and self._strikes(a, now) + self._strikes(b, now) >= FIGHT_STRIKES:
                    events.append(Event("fight", "Possible fight", "HIGH", (a, b), _union([da.box, db.box]), 0.6))
        return events

    def _speed(self, track_id: int, now: float) -> float:
        samples = self._recent(track_id, now, RUN_SECONDS)
        if len(samples) < 3 or samples[-1].t - samples[0].t < RUN_SECONDS * 0.7:
            return 0.0
        first, last = samples[0], samples[-1]
        distance = np.linalg.norm(_centre(last.box) - _centre(first.box))
        return distance / _height(last.box) / (last.t - first.t)

    def _running(self, visible, now) -> list[Event]:
        runners = [tid for tid in visible if self._speed(tid, now) > RUN_SPEED]
        if len(runners) < 2:
            return []
        return [Event("running", f"{len(runners)} people running — possible incident", "MEDIUM", tuple(runners),
                      _union([visible[t].box for t in runners]), 0.55)]
