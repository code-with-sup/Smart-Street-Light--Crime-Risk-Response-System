"""Camera tamper detection: covered / blinded, blurred, or turned away.

Every check compares the camera with its *own recent normal*, not a fixed number, so a street that
slowly gets dark at dusk is not "covered":

  covered  the picture suddenly becomes almost uniform (hand, tape, paper, spray, torch in the lens)
           while it was clearly detailed moments before                                   -> HIGH
  blurred  sharpness collapses to a fraction of its recent normal (lens smeared or sprayed) -> MEDIUM
  moved    most of the view stops matching the remembered scene (camera turned or knocked); a person
           walking past only changes part of it. After a while the new view is accepted.    -> MEDIUM
"""

from __future__ import annotations

from collections import deque

import cv2
import numpy as np

from .behavior import Event

COVERED_STD = 8.0          # grey-level spread of a lens covered by a hand / tape / paper
DETAILED_STD = 22.0        # a normal scene has at least this much spread
COVERED_SECONDS = 2.0
BLUR_RATIO = 0.15          # sharpness below 15 % of normal = blurred
BLUR_MIN_NORMAL = 40.0     # only judge blur on scenes that normally have detail
BLUR_SECONDS = 4.0
MOVED_DIFF = 0.8           # mean difference of normalised thumbnails; people walking past stay well under
MOVED_SECONDS = 5.0
ACCEPT_NEW_VIEW = 20.0     # after this long, a moved view becomes the new normal
HISTORY = 240              # samples of "normal" (about a minute at 4 per second)
RECENT = 20                # covering is judged against the last ~5 s, so a slow dusk fade never counts


def _normalise(gray_small: np.ndarray) -> np.ndarray:
    """Remove overall brightness / contrast so lights switching on don't look like a new scene."""
    g = gray_small.astype(np.float32)
    return (g - g.mean()) / (g.std() + 1e-3)


class TamperMonitor:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._std = deque(maxlen=HISTORY)
        self._sharp = deque(maxlen=HISTORY)
        self._reference: np.ndarray | None = None
        self._since = {"covered": None, "blurred": None, "moved": None}
        self.status = "ok"

    def _hold(self, kind: str, active: bool, now: float, seconds: float) -> bool:
        if not active:
            self._since[kind] = None
            return False
        self._since[kind] = self._since[kind] or now
        return now - self._since[kind] >= seconds

    def update(self, frame, now: float) -> list[Event]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (64, 36), interpolation=cv2.INTER_AREA)
        mid = cv2.resize(gray, (320, 180), interpolation=cv2.INTER_AREA)
        std = float(small.std())
        sharp = float(cv2.Laplacian(mid, cv2.CV_64F).var())
        recent = list(self._std)[-RECENT:]
        normal_std = float(np.median(recent)) if len(recent) >= 8 else None  # "sudden" = vs the last few seconds
        normal_sharp = float(np.median(self._sharp)) if len(self._sharp) >= 8 else None

        covered = self._hold("covered", std < COVERED_STD and normal_std is not None and normal_std > DETAILED_STD,
                             now, COVERED_SECONDS)
        blurred = not covered and self._hold(
            "blurred", normal_sharp is not None and normal_sharp > BLUR_MIN_NORMAL and sharp < BLUR_RATIO * normal_sharp
            and std >= COVERED_STD, now, BLUR_SECONDS)

        norm = _normalise(small)
        moved = False
        if self._reference is None:
            if std >= COVERED_STD:
                self._reference = norm
        elif not covered and std >= COVERED_STD:
            diff = float(np.abs(norm - self._reference).mean())
            changed = diff > MOVED_DIFF
            moved = self._hold("moved", changed, now, MOVED_SECONDS)
            if not changed:
                self._reference = 0.97 * self._reference + 0.03 * norm  # follow slow changes (light, shadows)
            elif self._since["moved"] and now - self._since["moved"] >= ACCEPT_NEW_VIEW:
                self._reference, self._since["moved"], moved = norm, None, False  # new normal view

        # only learn "normal" from healthy frames, so tampering never becomes the baseline
        if not (covered or blurred or self._since["covered"] or self._since["blurred"]):
            self._std.append(std)
            self._sharp.append(sharp)

        events = []
        if covered:
            events.append(Event("tamper_covered", "Camera covered or blinded — possible tampering", "HIGH", confidence=0.8))
        if blurred:
            events.append(Event("tamper_blurred", "Camera view blurred — lens smeared or sprayed?", "MEDIUM", confidence=0.6))
        if moved:
            events.append(Event("tamper_moved", "Camera view changed — camera moved or turned?", "MEDIUM", confidence=0.6))
        self.status = events[0].kind.replace("tamper_", "") if events else "ok"
        return events
