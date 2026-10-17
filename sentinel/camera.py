"""Webcam capture on its own thread so the UI never waits for a frame.

Set SENTINEL_VIDEO (or `run.py --video PATH`) to replay a video or image file instead of a webcam,
which is handy for demos and testing without a camera.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import cv2

if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)

MAX_PROBE_INDEX = 4
MAX_READ_FAILURES = 30


def _mac_devices() -> list[dict]:
    """Use the same AVFoundation device ordering as OpenCV, without opening cameras."""
    import objc

    objc.loadBundle("AVFoundation", {}, bundle_path="/System/Library/Frameworks/AVFoundation.framework")
    cls = objc.lookUpClass("AVCaptureDevice")
    devices = list(cls.devicesWithMediaType_("vide")) + list(cls.devicesWithMediaType_("muxx"))
    devices.sort(key=lambda device: str(device.uniqueID()))
    return [{"index": i, "id": str(device.uniqueID()), "name": str(device.localizedName())}
            for i, device in enumerate(devices[:10])]


def camera_devices() -> tuple[list[dict], str]:
    """List device names without taking over the current video feed."""
    if sys.platform == "darwin":
        try:
            devices = _mac_devices()
            return devices, "" if devices else "No cameras detected. Plug in your USB webcam, then refresh."
        except Exception:
            # Numbered inputs remain usable if native discovery is unavailable.
            pass
    elif sys.platform.startswith("linux"):
        devices = []
        for path in sorted(Path("/sys/class/video4linux").glob("video*")):
            try:
                index = int(path.name[5:])
                if index < 10:
                    devices.append({"index": index, "id": f"index:{index}", "name": path.joinpath("name").read_text().strip()})
            except (OSError, ValueError):
                continue
        if devices:
            return devices, ""
    return [{"index": i, "id": f"index:{i}", "name": f"Camera {i + 1}"} for i in range(MAX_PROBE_INDEX)], \
        "Camera names are unavailable. Try a numbered input; connect your USB webcam before refreshing."


def _open(index: int):
    """Open a camera that actually delivers a frame (macOS can open but not read)."""
    backends = []
    if sys.platform == "darwin" and hasattr(cv2, "CAP_AVFOUNDATION"):
        backends.append(cv2.CAP_AVFOUNDATION)
    else:
        backends.append(cv2.CAP_ANY)
    for backend in dict.fromkeys(backends):
        capture = cv2.VideoCapture(index, backend)
        if not capture.isOpened():
            capture.release()
            continue
        okay, frame = capture.read()
        if okay and frame is not None:
            return capture, frame
        capture.release()
    return None, None


class FileSource:
    """Loop a video (or hold a still image) at its native frame rate, like a live camera."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._image = cv2.imread(str(path)) if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp") else None
        self._capture = None if self._image is not None else cv2.VideoCapture(str(path))
        fps = self._capture.get(cv2.CAP_PROP_FPS) if self._capture else 0
        self._delay = 1 / fps if fps and fps < 120 else 1 / 25
        self._next = 0.0

    def isOpened(self) -> bool:  # same name as cv2.VideoCapture, so either can be used
        return self._image is not None or bool(self._capture and self._capture.isOpened())

    def read(self):
        wait = self._next - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._next = time.monotonic() + self._delay
        if self._image is not None:
            return True, self._image.copy()
        okay, frame = self._capture.read()
        if not okay:
            self._capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            okay, frame = self._capture.read()
        return okay, frame

    def release(self) -> None:
        if self._capture:
            self._capture.release()


def _video_override() -> Path | None:
    value = os.environ.get("SENTINEL_VIDEO", "").strip()
    return Path(value).expanduser() if value else None


class Camera:
    """One reader thread per camera session. Each thread owns its capture and releases it itself,
    so stop() never closes a device another thread is still reading. Start / switch / stop are
    serialised by one lifecycle lock (two tabs pressing Start cannot open the camera twice)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()          # guards the latest frame
        self._lifecycle = threading.RLock()    # guards start / switch / stop
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._frame = None
        self.frame_id = 0
        self.running = False
        self.index = 0
        self.device_id = ""
        self.name = ""
        self.mirror = False
        self.fps = 0.0
        self.error = ""
        self.size = (0, 0)

    def devices(self) -> dict:
        video = _video_override()
        if video is not None:
            return {"cameras": [], "demo": True, "message": f"Demo source: {video.name}",
                    "selected_index": self.index, "selected_id": self.device_id}
        cameras, message = camera_devices()
        return {"cameras": cameras, "demo": False, "message": message,
                "selected_index": self.index, "selected_id": self.device_id}

    def start(self, index: int | None = None, device_id: str | None = None) -> tuple[bool, str]:
        with self._lifecycle:
            video = _video_override()
            if video is not None:
                if index is not None or device_id:
                    return False, "Demo video is active. Restart without --video to use a webcam."
                if self.running:
                    return True, f"{self.name or 'Demo video'} already running"
                source = FileSource(video)
                okay, frame = source.read() if source.isOpened() else (False, None)
                if not okay:
                    source.release()
                    self.error = f"Could not read video file {video}"
                    return False, self.error
                self.name, self.device_id = video.name, ""
                self._begin(source, 0, frame)
                return True, f"Playing {video.name} as the camera"
            selected_id = device_id or (self.device_id if index is None else "")
            devices, _ = camera_devices()
            selected = next((d for d in devices if d["id"] == selected_id), None) if selected_id else None
            if selected_id and selected is None:
                return False, "The selected camera is disconnected. Plug it in and refresh the camera list."
            preferred = selected["index"] if selected else self.index if index is None else index
            if self.running and (selected_id == self.device_id if selected_id else preferred == self.index):
                return True, f"{self.name or f'Camera {self.index + 1}'} already running"
            # Explicit selection must never silently fall back to a different camera.
            order = [preferred] if index is not None or selected_id else [preferred] + [i for i in range(MAX_PROBE_INDEX) if i != preferred]
            for candidate in order:
                capture, frame = _open(candidate)
                if capture is not None:
                    chosen = next((d for d in devices if d["index"] == candidate), None)
                    # Keep the working source until the new camera delivers its first frame.
                    self._stop_locked()
                    self.name = chosen["name"] if chosen else f"Camera {candidate + 1}"
                    self.device_id = chosen["id"] if chosen else ""
                    self._begin(capture, candidate, frame)
                    return True, f"{self.name} connected"
            self.error = ("The selected camera could not deliver a frame. Close other apps using it and allow camera "
                          "access in System Settings > Privacy & Security > Camera, then try again.")
            return False, self.error

    def switch(self) -> tuple[bool, str]:
        with self._lifecycle:
            if _video_override() is not None:
                return False, "Demo video is playing; there is no other camera to switch to"
            devices, _ = camera_devices()
            candidates = [d for d in devices if d["id"] != self.device_id and d["index"] != self.index]
            for device in candidates:
                okay, message = self.start(device["index"], device["id"])
                if okay:
                    return okay, message
            return False, "No other camera is available. Plug in your USB webcam and refresh."

    def _begin(self, capture, index: int, frame) -> None:
        stop_event = threading.Event()
        self._stop_event = stop_event
        self.index = index
        self.error = ""
        self.running = True
        self._publish(frame)
        self._thread = threading.Thread(target=self._loop, args=(capture, stop_event), name="camera", daemon=True)
        self._thread.start()

    def _publish(self, frame) -> None:
        if self.mirror:
            frame = cv2.flip(frame, 1)
        with self._lock:
            self._frame = frame
            self.frame_id += 1
            self.size = (frame.shape[1], frame.shape[0])

    def _loop(self, capture, stop_event: threading.Event) -> None:
        failures, count, window_start = 0, 0, time.monotonic()
        try:
            while not stop_event.is_set():
                okay, frame = capture.read()
                if stop_event.is_set():
                    break
                if not okay or frame is None:
                    failures += 1
                    if failures >= MAX_READ_FAILURES:
                        self.error = "The camera stopped sending frames."
                        break
                    time.sleep(0.03)
                    continue
                failures = 0
                self._publish(frame)
                count += 1
                elapsed = time.monotonic() - window_start
                if elapsed >= 1.0:
                    self.fps = count / elapsed
                    count, window_start = 0, time.monotonic()
        finally:
            capture.release()
            self._ended_by_itself(stop_event)

    def _ended_by_itself(self, stop_event: threading.Event) -> None:
        """Camera died (not stopped): mark the session over, unless stop() or a newer session took over.
        stop() holds the lifecycle lock while joining this thread, so never block on it here."""
        while not stop_event.is_set():
            if self._lifecycle.acquire(timeout=0.1):
                try:
                    if stop_event is self._stop_event:
                        self._stop_event = None
                        self.running = False
                        self._clear()
                finally:
                    self._lifecycle.release()
                return

    def _clear(self) -> None:
        with self._lock:
            self._frame = None
        self.fps = 0.0

    def stop(self) -> None:
        with self._lifecycle:
            self._stop_locked()

    def _stop_locked(self) -> None:
        stop_event, thread = self._stop_event, self._thread
        self._stop_event, self._thread = None, None
        if stop_event is not None:
            stop_event.set()
        self.running = False
        if thread and thread.is_alive() and thread is not threading.current_thread():
            # if a read is stuck, the thread still releases its own capture once the read returns
            thread.join(timeout=5)
        self._clear()

    def latest(self):
        with self._lock:
            return self.frame_id, self._frame
