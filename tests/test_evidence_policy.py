import time
import numpy as np
import pytest
from sentinel import alerts
from sentinel.behavior import Event
from sentinel.detection import Detection
from sentinel.risk import RiskResult


@pytest.mark.parametrize("scenario,expected", [
    ("night", False), ("crowd", False), ("sos", False), ("tamper", False),
    ("held", False), ("weapon", True), ("crime", True), ("fight", True),
])
def test_only_threats_save_media(service, monkeypatch, scenario, expected):
    photos, clips = [], []
    monkeypatch.setattr("sentinel.service.cv2.imwrite", lambda *a, **k: photos.append(a[0]) or True)
    monkeypatch.setattr(service.clips, "capture", lambda *a: clips.append(a))
    service.events = []
    detections = []
    result = RiskResult(level="MEDIUM", reasons=["Night activity"])
    if scenario not in ("night", "crowd"):
        result.level = "HIGH"
    if scenario in ("weapon", "held"):
        result.weapon = Detection((0, 0, 20, 20), "knife", .9, "weapon")
        if scenario == "weapon": detections = [result.weapon]
    if scenario == "crime":
        detections = [Detection((0, 0, 20, 20), "fight", .9, "event")]
        result.event = Event("model", "Fight detected", "HIGH")
    if scenario in ("fight", "sos", "tamper"):
        result.event = Event(scenario, scenario, "HIGH")
        service.events = [result.event]
    service._record_incident(result, detections, np.zeros((48, 64, 3), np.uint8), sos=scenario == "sos")
    assert bool(photos) == expected
    assert bool(clips) == expected


def test_normal_heatmap_does_not_save_images(service, monkeypatch):
    writes = []
    monkeypatch.setattr("sentinel.service.cv2.imwrite", lambda *a, **k: writes.append(a) or True)
    service.events = []
    service._heat_bg_at = 0
    service._add_heat([Detection((0, 0, 20, 20), "person", .9, "person")],
                      np.zeros((48, 64, 3), np.uint8), time.time())
    assert not writes


def test_phone_is_manual_and_address_validated():
    assert alerts.validate_address("phone", "+919876543210") is None
    assert alerts.validate_address("phone", "invalid")
    assert alerts.channel_status()["phone"]["configured"] is False


def test_manual_phone_not_used_for_automatic_alerts(service):
    service.store.add_contact("Emergency", "phone", "+919876543210")
    service.settings["alert_mode"] = "auto"
    det = Detection((0, 0, 20, 20), "knife", .9, "weapon")
    service._record_incident(RiskResult(level="HIGH", reasons=["Knife"], weapon=det), [det], None)
    assert service.notifier.sent == []
    assert service.store.incidents()[0]["alert_status"] == "no_contacts"
