"""Automatic weapon SOS requires live, continuous evidence; notifications are fake."""
import pytest
from sentinel.detection import Detection


def setup_weapon(service, monkeypatch, mode='manual'):
    clock = [0.0]
    monkeypatch.setattr('sentinel.service.time.monotonic', lambda: clock[0])
    service.settings['alert_mode'] = mode
    service.store.add_contact('Test', 'email', 'test@example.com')
    service.detector.output = [Detection((5, 5, 30, 40), 'knife', .9, 'weapon')]
    return clock


@pytest.mark.parametrize('mode', ['manual', 'auto'])
def test_only_after_thirty_seconds_and_once_per_episode(service, monkeypatch, mode):
    clock = setup_weapon(service, monkeypatch, mode)
    last = 0
    for second in range(31):
        clock[0] = second
        last = service._tick(last)
    assert service.notifier.sent == []  # exactly 30 seconds is not more than 30
    clock[0] = 31
    last = service._tick(last)
    assert len(service.notifier.sent) == 1
    assert 'SOS' in service.notifier.sent[0][1]
    for second in range(32, 45):
        clock[0] = second
        last = service._tick(last)
    assert len(service.notifier.sent) == 1


def test_disappearance_resets_even_while_risk_is_held_high(service, monkeypatch):
    clock = setup_weapon(service, monkeypatch)
    last = 0
    for second in range(30):
        clock[0] = second
        last = service._tick(last)
    service.detector.output = []
    clock[0] = 30
    last = service._tick(last)
    assert service.result.level == 'HIGH'  # risk hold does not keep the SOS timer alive
    service.detector.output = [Detection((5, 5, 30, 40), 'scissors', .9, 'weapon')]
    for second in range(31, 62):
        clock[0] = second
        last = service._tick(last)
    assert not service.notifier.sent
    clock[0] = 62
    service._tick(last)
    assert len(service.notifier.sent) == 1


def test_camera_off_cancels_timer_and_pending_alerts(service, monkeypatch):
    clock = setup_weapon(service, monkeypatch)
    last = 0
    for second in range(30):
        clock[0] = second
        last = service._tick(last)
    service.camera.stop()
    clock[0] = 50
    service._tick(last)
    assert service._weapon_visible_since is None
    assert not service.notifier.sent


def test_stale_or_interrupted_frame_cannot_complete_timer(service, monkeypatch):
    clock = setup_weapon(service, monkeypatch)
    last = 0
    for second in range(30):
        clock[0] = second
        last = service._tick(last)
    clock[0] = 40  # a fresh frame after a long gap starts a new episode
    service._tick(last)
    assert not service.notifier.sent
    assert service._weapon_visible_since == 40


def test_low_confidence_and_tools_never_count(service, monkeypatch):
    setup_weapon(service, monkeypatch)
    service._observe_weapon_presence([Detection((0, 0, 20, 20), 'knife', .01, 'weapon')], active=True)
    assert service._weapon_visible_since is None
    service._observe_weapon_presence([Detection((0, 0, 20, 20), 'hammer', .9, 'tool')], active=True)
    assert service._weapon_visible_since is None


def test_manual_send_is_not_duplicated_at_thirty_seconds(service, monkeypatch):
    clock = setup_weapon(service, monkeypatch)
    last = 0
    for second in range(3):
        clock[0] = second
        last = service._tick(last)
    service.dispatch_alert(service.store.incidents(level='HIGH')[0]['id'])
    for second in range(3, 33):
        clock[0] = second
        last = service._tick(last)
    assert len(service.notifier.sent) == 1


def test_stalled_camera_clears_presence_even_if_last_box_was_weapon(service, monkeypatch):
    clock = setup_weapon(service, monkeypatch)
    last = 0
    for second in range(30):
        clock[0] = second
        last = service._tick(last)
    service.camera.fresh = False
    service._last_fresh -= 5
    clock[0] = 40
    service._tick(last)
    assert service._weapon_visible_since is None
    assert not service.notifier.sent
