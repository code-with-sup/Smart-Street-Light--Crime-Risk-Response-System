"""Video evidence: a short clip around each incident (a few seconds before and after).

A sampler thread keeps the last few seconds of annotated camera frames (as JPEG, to keep memory
small). When an incident is recorded, the clip takes that pre-roll, keeps collecting for the
post-roll, then encodes a browser-playable video next to the snapshot in data/evidence/.

Browsers play H.264 MP4 and VP8 WebM but not OpenCV's default "mp4v"; the first format this
machine can write is used, and if none works no clip is saved (the snapshot is still there).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger("sentinel.clips")

FORMATS = (("mp4", "avc1"), ("webm", "VP80"))  # in order of preference; both play in browsers


@dataclass
class _Pending:
    incident_id: int
    stem: str
    until: float
    frames: list = field(default_factory=list)  # (ts, jpeg bytes)


class ClipRecorder:
    def __init__(self, folder: Path, on_saved: Callable[[int, str], None], *, fps: int = 10,
                 before: float = 5.0, after: float = 5.0, max_width: int = 960) -> None:
        self.folder, self.on_saved = folder, on_saved
        self.fps, self.before, self.after, self.max_width = fps, before, after, max_width
        self._buffer: deque = deque(maxlen=int(fps * before) + 1)
        self._pending: list[_Pending] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._format: tuple[str, str] | bool | None = False  # False = not probed yet, None = no encoder

    # ------------------------------------------------------------ capture
    def start(self, grab: Callable[[], object]) -> None:
        """`grab()` returns the current annotated BGR frame, or None when the camera is off."""
        self._running = True
        self._thread = threading.Thread(target=self._sample, args=(grab,), name="clip-sampler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        with self._lock:
            pending, self._pending = self._pending, []
        for clip in pending:  # shutting down: save what we have rather than lose the evidence
            self._encode(clip)

    def _sample(self, grab) -> None:
        step = 1.0 / self.fps
        while self._running:
            started = time.monotonic()
            try:
                frame = grab()
                if frame is not None:
                    self.add(frame, time.time())
                else:
                    self._buffer.clear()  # camera off: no pre-roll from an old session
            except Exception:
                log.exception("clip sampling failed")
            time.sleep(max(0.0, step - (time.monotonic() - started)))

    def add(self, frame, ts: float) -> None:
        h, w = frame.shape[:2]
        if w > self.max_width:
            frame = cv2.resize(frame, (self.max_width, int(h * self.max_width / w)), interpolation=cv2.INTER_AREA)
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return
        item = (ts, buffer.tobytes())
        done = []
        with self._lock:
            self._buffer.append(item)
            for clip in self._pending:
                clip.frames.append(item)
                if ts >= clip.until:
                    done.append(clip)
            self._pending = [c for c in self._pending if c not in done]
        for clip in done:
            threading.Thread(target=self._encode, args=(clip,), name="clip-encode", daemon=True).start()

    def capture(self, incident_id: int, stem: str) -> None:
        """Start a clip for this incident: the buffered pre-roll plus `after` seconds from now."""
        with self._lock:
            clip = _Pending(incident_id, stem, time.time() + self.after, list(self._buffer))
            self._pending.append(clip)

    # ------------------------------------------------------------- encode
    def _writer(self, path_stem: Path, size: tuple[int, int]):
        formats = FORMATS if self._format is False else ([self._format] if self._format else [])
        for ext, fourcc in formats:
            path = path_stem.with_suffix(f".{ext}")
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*fourcc), self.fps, size)
            if writer.isOpened():
                self._format = (ext, fourcc)
                return writer, path
            writer.release()
            path.unlink(missing_ok=True)
        self._format = None
        return None, None

    def _encode(self, clip: _Pending) -> None:
        if len(clip.frames) < 2:
            return
        try:
            first = cv2.imdecode(np.frombuffer(clip.frames[0][1], np.uint8), cv2.IMREAD_COLOR)
            size = (first.shape[1], first.shape[0])
            writer, path = self._writer(self.folder / clip.stem, size)
            if writer is None:
                log.warning("no browser-playable video encoder available; clip for incident %s skipped", clip.incident_id)
                return
            for _ts, data in clip.frames:
                frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                if frame.shape[1] != size[0] or frame.shape[0] != size[1]:
                    frame = cv2.resize(frame, size)  # camera switched mid-clip
                writer.write(frame)
            writer.release()
            self.on_saved(clip.incident_id, path.name)
        except Exception:
            log.exception("could not save clip for incident %s", clip.incident_id)
