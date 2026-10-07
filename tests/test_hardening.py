"""Regression tests for the issues found in the backend review: camera lifecycle, stalled frames,
loitering, the HIGH -> incident -> alert path, settings coercion and API input guards."""

import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from sentinel import camera as camera_mod
from sentinel.config import DEFAULT_SETTINGS
from sentinel.detection import Detection
from sentinel.risk import RiskEngine
from sentinel.service import Sentinel, SettingsError, _coerce

SETTINGS = dict(DEFAULT_SETTINGS)
FRAME = np.zeros((48, 64, 3), dtype=np.uint8)


def person(track_id=None):
    return Detection((0, 0, 10, 10), "person", 0.9, "person", track_id)


def knife():
    return Detection((0, 0, 5, 5), "knife", 0.8, "weapon")


# ------------------------------------------------------------------ risk
def test_lingering_survives_flickering_detections():
    engine = RiskEngine()
    result = None
    for i in range(400):  # 100 s at 4 passes/s, the person missed in 1 pass out of 20
        dets = [] if i % 20 == 19 else [person()]
        result = engine.evaluate(dets, is_night=True, motion=False, settings=SETTINGS, now=1000 + i * 0.25)
    assert any("lingering" in r for r in result.reasons)


def test_lingering_is_timed_per_tracked_person():
    engine = RiskEngine()
    # person 1 stays the whole time, a stream of passers-by (2, 3, 4...) come and go
    for i in range(0, 70):
        dets = [person(1), person(100 + i // 5)]
        result = engine.evaluate(dets, is_night=True, motion=False, settings=SETTINGS, now=1000 + i)
    assert any("Person #1 lingering" in r for r in result.reasons)


def test_busy_street_of_short_visits_is_not_lingering():
    engine = RiskEngine()
    for i in range(0, 90):
        result = engine.evaluate([person(200 + i // 10)], is_night=True, motion=False, settings=SETTINGS, now=1000 + i)
    assert not any("lingering" in r for r in result.reasons)


# --------------------------------------------------------------- settings
@pytest.mark.parametrize("key,value", [("mirror", "false"), ("crowd_threshold", 2.9), ("confidence", float("nan")),
                                       ("crowd_threshold", True)])
def test_loose_setting_values_are_rejected(key, value):
    with pytest.raises(SettingsError):
        _coerce(key, value)


# ----------------------------------------------------------------- camera
class FakeCapture:
    def __init__(self, fail_after=None):
        self.reads, self.released, self.fail_after = 0, False, fail_after

    def isOpened(self):
        return True

    def read(self):
        self.reads += 1
        time.sleep(0.005)
        if self.fail_after is not None and self.reads > self.fail_after:
            return False, None
        return True, FRAME.copy()

    def release(self):
        self.released = True


def test_concurrent_starts_open_the_camera_once(monkeypatch):
    opened = []

    def fake_open(index):
        time.sleep(0.05)
        cap = FakeCapture()
        opened.append(cap)
        return cap, FRAME

    monkeypatch.setattr(camera_mod, "_open", fake_open)
    monkeypatch.delenv("SENTINEL_VIDEO", raising=False)
    cam = camera_mod.Camera()
    threads = [threading.Thread(target=cam.start) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(opened) == 1 and cam.running
    cam.stop()
    assert opened[0].released and not cam.running and cam.latest()[1] is None


def test_camera_that_dies_clears_its_frame(monkeypatch):
    cap = FakeCapture(fail_after=3)
    monkeypatch.setattr(camera_mod, "_open", lambda index: (cap, FRAME))
    monkeypatch.delenv("SENTINEL_VIDEO", raising=False)
    cam = camera_mod.Camera()
    cam.start()
    deadline = time.time() + 5
    while cam.running and time.time() < deadline:
        time.sleep(0.02)
    assert not cam.running and cam.latest()[1] is None and cap.released and cam.error


# ---------------------------------------------------------------- service
class FakeDetector:
    ready, tracking, model_name, models, device, error = True, False, "fake", ["fake"], "cpu", ""

    def __init__(self):
        self.output = []

    def detect(self, frame, confidence, weapon_confidence):
        return list(self.output)

    def reset_tracks(self):
        pass


class FakeCamera:
    running, index, fps, mirror, size, error = True, 0, 0.0, False, (64, 48), ""

    def __init__(self):
        self.frame_id = 0
        self.fresh = True

    def latest(self):
        if self.fresh:
            self.frame_id += 1
        return self.frame_id, FRAME

    def stop(self):
        self.running = False


class SyncNotifier:
    def __init__(self):
        self.sent = []

    def send(self, contact, subject, body, image=None):
        self.sent.append((contact["address"], subject))
        return True, ""

    def submit(self, fn, *args):
        fn(*args)

    def shutdown(self):
        pass


@pytest.fixture
def service():
    s = Sentinel()
    s.detector, s.camera, s.notifier = FakeDetector(), FakeCamera(), SyncNotifier()
    s.settings = s.store.save_settings({**DEFAULT_SETTINGS, "night_start": "00:00", "night_end": "23:59",
                                        "incident_cooldown_s": 5})  # fresh settings: tests share one temp database
    yield s
    for item in s.store.incidents(limit=None):
        s.store.delete_incident(item["id"])
    for contact in s.store.contacts():
        s.store.delete_contact(contact["id"])


def test_weapon_raises_high_incident_and_auto_alert_is_sent(service):
    service.store.add_contact("Control room", "email", "control@example.com")
    service.settings = service.store.save_settings({"alert_mode": "auto"})
    service.detector.output = [person(), knife()]
    last = 0
    for _ in range(3):
        last = service._tick(last)
    assert service.result.level == "HIGH" and service.hardware.buzzer
    high = service.store.incidents(level="HIGH")
    assert len(high) == 1 and high[0]["snapshot"] and high[0]["alert_status"] == "sent"
    assert service.notifier.sent and "knife" in service.notifier.sent[0][1]


def test_auto_alert_inside_cooldown_is_marked_suppressed(service):
    service.store.add_contact("Control room", "email", "control@example.com")
    service.settings = service.store.save_settings({"alert_mode": "auto", "alert_cooldown_s": 600, "incident_cooldown_s": 5})
    service._last_auto_alert = time.time()  # an alert just went out
    service.detector.output = [person(), knife()]
    last = 0
    for _ in range(3):
        last = service._tick(last)
    assert service.store.incidents(level="HIGH")[0]["alert_status"] == "suppressed"
    assert not service.notifier.sent


def test_manual_mode_waits_for_operator(service):
    service.store.add_contact("Control room", "email", "control@example.com")
    service.detector.output = [knife()]
    last = 0
    for _ in range(3):
        last = service._tick(last)
    incident = service.store.incidents(level="HIGH")[0]
    assert incident["alert_status"] == "pending" and not service.notifier.sent
    service.dispatch_alert(incident["id"])
    assert service.store.incident(incident["id"])["alert_status"] == "sent"


def test_stalled_camera_still_drives_lamp_and_expires_risk(service):
    service.detector.output = [person()]
    last = service._tick(0)
    assert service.result.level == "MEDIUM"
    service.camera.fresh = False  # camera "running" but frozen
    service._last_fresh = time.time() - 10
    service.detector.output = []
    service._tick(last)
    assert service.result.level == "LOW"  # not stuck on the stale frame


# -------------------------------------------------------------------- API
@pytest.fixture
def client():
    from sentinel.server import app
    return TestClient(app)  # no context manager: the background service is not started


def test_nan_location_is_rejected(client):
    response = client.put("/api/location", content='{"lat": 1, "lng": 2, "accuracy": NaN}',
                          headers={"content-type": "application/json"})
    assert response.status_code == 422
    assert client.get("/api/settings").status_code == 200


def test_absurd_report_range_is_a_400(client):
    assert client.get("/api/reports/csv?start=2026-01-01&end=9999-12-31").status_code == 400


def test_evidence_directory_is_not_served(client):
    # %2E%2E reaches the route as ".." (a plain "/evidence/.." is normalised away by the HTTP client)
    assert client.get("/evidence/%2E%2E").status_code == 404


def test_single_incident_endpoint_404s(client):
    assert client.get("/api/incidents/999999").status_code == 404


# ------------------------------------------------------------- real model
def test_model_swap_while_detecting_does_not_crash_gpu():
    """Loading a model while another thread runs inference used to abort the process on Apple GPUs
    (Metal: 'A command encoder is already encoding to this command buffer')."""
    from sentinel.config import ROOT
    from sentinel.detection import Detector

    if not (ROOT / "yolo11n.pt").exists():
        pytest.skip("yolo11n.pt not present")
    first = Detector("yolo11n")
    assert first.ready, first.error
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    stop = threading.Event()
    errors = []

    def run():
        while not stop.is_set():
            try:
                first.detect(frame, 0.4, 0.45)
            except Exception as error:  # pragma: no cover - surfaced below
                errors.append(error)

    worker = threading.Thread(target=run)
    worker.start()
    try:
        second = Detector("yolo11n")  # warms up on the same GPU while `run` is busy
    finally:
        stop.set()
        worker.join()
    assert second.ready and not errors
