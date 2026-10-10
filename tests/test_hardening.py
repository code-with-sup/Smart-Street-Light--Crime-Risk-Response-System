"""Regression tests for the issues found in the backend review: camera lifecycle, stalled frames,
loitering, the HIGH -> incident -> alert path, settings coercion and API input guards."""

import threading
import time

import numpy as np
import pytest

from sentinel import camera as camera_mod
from sentinel.config import DEFAULT_SETTINGS
from sentinel.detection import Detection
from sentinel.risk import RiskEngine
from sentinel.service import SettingsError, _coerce

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
def test_weapon_raises_high_incident_and_auto_alert_waits_for_presence(service):
    service.store.add_contact("Control room", "email", "control@example.com")
    service.settings = service.store.save_settings({"alert_mode": "auto"})
    service.detector.output = [person(), knife()]
    last = 0
    for _ in range(3):
        last = service._tick(last)
    assert service.result.level == "HIGH" and service.hardware.buzzer
    high = service.store.incidents(level="HIGH")
    assert len(high) == 1 and high[0]["snapshot"] and high[0]["alert_status"] == "pending"
    assert not service.notifier.sent


def test_auto_alert_inside_cooldown_is_marked_suppressed(service):
    service.store.add_contact("Control room", "email", "control@example.com")
    service.settings = service.store.save_settings({"alert_mode": "auto", "alert_cooldown_s": 600, "incident_cooldown_s": 5})
    service._last_auto_alert = time.time()  # an alert just went out
    service.detector.output = [person(), Detection((0, 0, 20, 20), "fight", .9, "event")]
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


# ------------------------------------------------------------- SOS + strobe
def test_esp32_sos_line_and_strobe_state_are_parsed():
    from sentinel.hardware import HardwareLink

    link = HardwareLink()
    link._handle_line("STATE 0 900 100 1 1")
    assert link.strobe
    link._handle_line("SOS")
    assert link.take_sos() and not link.take_sos()  # once per press


def test_set_command_carries_strobe():
    from sentinel.hardware import HardwareLink

    link, sent = HardwareLink(), []
    link.mode, link._write = "serial", sent.append
    link.drive(100, True, people=1, is_night_clock=True, strobe=True)
    assert sent[-1] == "SET 100 1 1"


def test_sos_press_raises_high_records_and_alerts_even_in_manual_mode(service):
    service.store.add_contact("Control room", "email", "control@example.com")
    assert service.settings["alert_mode"] == "manual"
    service.camera.running = False
    service.hardware.press_sos()
    service._tick(0)
    assert service.result.level == "HIGH" and service.hardware.buzzer and service.hardware.strobe
    sos = service.store.incidents(level="HIGH")[0]
    assert sos["label"] == "sos" and sos["alert_status"] == "sent"
    assert service.notifier.sent and "SOS" in service.notifier.sent[0][1]


def test_clearing_sos_lets_risk_fall_back(service):
    service.camera.running = False
    service.hardware.press_sos()
    service._tick(0)
    service.clear_sos()
    service.risk.reset()  # skip the 8 s anti-flicker hold
    service._tick(0)
    assert service.result.level != "HIGH" and not service.hardware.strobe


def test_strobe_can_be_switched_off(service):
    service.settings = service.store.save_settings({"strobe_on_high": False})
    service.camera.running = False
    service.hardware.press_sos()
    service._tick(0)
    assert service.result.level == "HIGH" and not service.hardware.strobe


# ------------------------------------------------------------- video clips
def test_clip_recorder_saves_playable_clip_with_pre_and_post_roll(tmp_path):
    import cv2

    from sentinel.clips import ClipRecorder

    saved = []
    recorder = ClipRecorder(tmp_path, lambda incident_id, name: saved.append((incident_id, name)),
                            fps=10, before=0.5, after=0.5)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    t0 = 1000.0
    for i in range(10):  # 1 s of pre-roll history; only the last ~0.5 s is kept
        recorder.add(frame, t0 + i * 0.1)
    recorder.capture(7, "clip_test")
    until = recorder._pending[0].until
    ts = until - 0.5
    while recorder._pending:
        recorder.add(frame, ts)
        ts += 0.1
    deadline = time.time() + 10
    while not saved and time.time() < deadline:
        time.sleep(0.05)
    assert saved and saved[0][0] == 7
    capture = cv2.VideoCapture(str(tmp_path / saved[0][1]))
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    assert saved[0][1].endswith((".mp4", ".webm")) and frames >= 8  # ~5 pre-roll + ~6 post-roll


def test_old_database_gets_clip_column_and_clip_files_are_deleted(tmp_path):
    import sqlite3

    from sentinel import storage

    db = tmp_path / "old.db"
    old = sqlite3.connect(db)
    old.executescript(storage.SCHEMA)  # the original schema has no clip column; Store() must add it
    old.close()
    store = storage.Store(db)
    incident = store.add_incident(ts=time.time(), level="HIGH", label="weapon", confidence=0.7, people=1, vehicles=0,
                                  reasons=["x"], snapshot=None, lat=None, lng=None, alert_status="none")
    clip = storage.EVIDENCE_DIR / "test_clip.mp4"
    clip.write_bytes(b"x")
    store.set_clip(incident["id"], clip.name)
    assert store.incident(incident["id"])["clip_url"] == "/evidence/test_clip.mp4"
    store.delete_incident(incident["id"])
    assert not clip.exists()


# ------------------------------------------------------------- energy + escalation
def test_energy_counts_dimmed_lamp_against_full_night_baseline(service):
    service.settings = service.store.save_settings({"lamp_watts": 100, "tariff_per_kwh": 10.0})
    service.is_night = True
    service.hardware.brightness = 20
    t = time.time()
    service._energy["t"] = t
    for i in range(1, 3601):  # one simulated hour at 1 s steps
        service._account_energy(t + i)
    service._flush_energy()
    from datetime import datetime
    day = datetime.fromtimestamp(t + 1800, service.tz).strftime("%Y-%m-%d")
    summary = service._energy_summary([day])
    # baseline 100 W x 1 h = 0.1 kWh; dimmed lamp 20 W x 1 h = 0.02 kWh -> 0.08 kWh saved
    assert summary["baseline_kwh"][0] == pytest.approx(0.1, rel=0.02)
    assert summary["lamp_kwh"][0] == pytest.approx(0.02, rel=0.02)
    assert summary["saving_pct"] == pytest.approx(80, abs=1)
    assert summary["saved_cost"] == pytest.approx(0.8, rel=0.05)


def test_energy_ignores_gaps_in_the_loop(service):
    service.is_night, service.hardware.brightness = True, 100
    service._energy.update(t=1000.0, lamp_wh=0.0, baseline_wh=0.0, day="")
    service._account_energy(1000.0 + 3600)  # the laptop slept for an hour: count at most 2 s
    assert service._energy["baseline_wh"] < 1


def test_old_pending_high_alert_is_not_replayed_after_restart(service):
    service.store.add_contact("Control room", "email", "control@example.com")
    service.settings = service.store.save_settings({"escalate_after_min": 5})
    incident = service.store.add_incident(ts=time.time() - 400, level="HIGH", label="weapon", confidence=0.7, people=1,
                                          vehicles=0, reasons=["Weapon detected"], snapshot=None, lat=None, lng=None,
                                          alert_status="pending")
    service._housekeeping(service.result, [], time.time())
    assert service.store.incident(incident["id"])["alert_status"] == "pending"
    assert not service.notifier.sent


def test_recent_pending_alert_is_not_escalated_yet(service):
    service.store.add_contact("Control room", "email", "control@example.com")
    incident = service.store.add_incident(ts=time.time() - 60, level="HIGH", label="weapon", confidence=0.7, people=1,
                                          vehicles=0, reasons=["x"], snapshot=None, lat=None, lng=None, alert_status="pending")
    service._housekeeping(service.result, [], time.time())
    assert service.store.incident(incident["id"])["alert_status"] == "pending"


# ------------------------------------------------------------------ zones
def test_person_entering_a_high_zone_raises_high_with_the_zone_name(service):
    service.settings = service.store.save_settings({"night_start": "00:00", "night_end": "00:01"})  # daytime
    service.set_zones([{"name": "ATM", "type": "area", "rule": "no_entry", "level": "HIGH",
                        "points": [[0.5, 0.5], [1, 0.5], [1, 1], [0.5, 1]]}])
    w, h = service.camera.size
    outside = Detection((5, 5, 15, int(h * 0.3)), "person", 0.9, "person", 1)
    inside = Detection((int(w * 0.7), int(h * 0.4), int(w * 0.8), int(h * 0.9)), "person", 0.9, "person", 1)
    service.detector.output = [outside]
    last = service._tick(0)
    assert service.result.level == "LOW"
    service.detector.output = [inside]
    service._tick(last)
    assert service.result.level == "HIGH" and "entered ATM" in service.result.reasons[0]
    assert service.store.incidents(level="HIGH")[0]["label"].startswith("person #1 entered atm")


def test_zone_api_rejects_bad_zones(client):
    bad = client.put("/api/zones", json=[{"type": "line", "points": [[0, 0]]}])
    assert bad.status_code == 400 and "2 points" in bad.json()["detail"]


def test_model_list_only_offers_models_on_this_computer(client):
    from sentinel.config import ROOT

    data = client.get("/api/models").json()
    current = client.get("/api/settings").json()["model"]
    assert data["models"] and all(m["id"] == current or (ROOT / f"{m['id']}.pt").exists() for m in data["models"])
    assert isinstance(data["always_on"], list)
