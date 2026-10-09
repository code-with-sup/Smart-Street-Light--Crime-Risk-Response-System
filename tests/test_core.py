import pytest

from sentinel.config import DEFAULT_SETTINGS
from sentinel.detection import Detection
from sentinel.hardware import HardwareLink
from sentinel.risk import HIGH_HOLD_SECONDS, RiskEngine
from sentinel.service import SettingsError, _coerce

SETTINGS = dict(DEFAULT_SETTINGS)


def person():
    return Detection((0, 0, 10, 10), "person", 0.9, "person")


def knife(conf=0.8):
    return Detection((0, 0, 5, 5), "knife", conf, "weapon")


def run(engine, detections, *, night=False, motion=False, t=1000.0):
    return engine.evaluate(detections, is_night=night, motion=motion, settings=SETTINGS, now=t)


def test_empty_street_by_day_is_low_and_light_off():
    result = run(RiskEngine(), [])
    assert (result.level, result.brightness, result.buzzer) == ("LOW", 0, False)


def test_empty_street_at_night_is_dimmed():
    result = run(RiskEngine(), [], night=True)
    assert (result.level, result.brightness) == ("LOW", SETTINGS["low_brightness"])


def test_person_at_night_is_medium_full_light():
    result = run(RiskEngine(), [person()], night=True)
    assert (result.level, result.brightness, result.buzzer) == ("MEDIUM", 100, False)


def test_pir_motion_at_night_without_camera_is_medium():
    assert run(RiskEngine(), [], night=True, motion=True).level == "MEDIUM"


def test_person_by_day_stays_low():
    assert run(RiskEngine(), [person()]).level == "LOW"


def test_crowd_is_medium_even_by_day():
    crowd = [person() for _ in range(SETTINGS["crowd_threshold"])]
    assert run(RiskEngine(), crowd).level == "MEDIUM"


def test_lingering_at_night_adds_reason():
    engine = RiskEngine()
    run(engine, [person()], night=True, t=1000)
    result = run(engine, [person()], night=True, t=1000 + SETTINGS["loiter_seconds"])
    assert any("lingering" in reason for reason in result.reasons)


def test_single_weapon_frame_is_not_enough_for_high():
    assert run(RiskEngine(), [person(), knife()]).level != "HIGH"


def test_weapon_in_two_of_three_passes_is_high_with_buzzer():
    engine = RiskEngine()
    run(engine, [knife()], t=1000)
    run(engine, [], t=1001)
    result = run(engine, [knife(0.7)], t=1002)
    assert (result.level, result.brightness, result.buzzer) == ("HIGH", 100, True)
    assert result.weapon.label == "knife"
    assert result.score >= 70


def test_high_holds_briefly_then_drops():
    engine = RiskEngine()
    run(engine, [knife()], t=1000)
    run(engine, [knife()], t=1001)
    assert run(engine, [], t=1002).level == "HIGH"
    assert run(engine, [], t=1001 + HIGH_HOLD_SECONDS + 1).level == "LOW"


def test_esp32_state_line_is_parsed():
    link = HardwareLink()
    link._handle_line("STATE 1 812 100 1")
    assert (link.pir, link.ldr, link.brightness, link.buzzer) == (True, 812, 100, True)
    link._handle_line("READY sentinel-esp32 v1")
    assert link.firmware == "sentinel-esp32 v1"
    link._handle_line("STATE garbage")  # ignored, no crash


def test_simulator_follows_requested_output_and_override():
    link = HardwareLink()
    link.drive(20, False, people=0, is_night_clock=True)
    assert (link.brightness, link.buzzer, link.pir) == (20, False, False)
    link.test_output(100, True, 5)
    link.drive(0, False, people=1, is_night_clock=True)
    assert (link.brightness, link.buzzer, link.pir) == (100, True, True)


@pytest.mark.parametrize("key,value", [
    ("night_start", "25:00"), ("confidence", 1.5), ("alert_mode", "sometimes"),
    ("time_zone", "Mars/Olympus"), ("crowd_threshold", "lots"),
])
def test_invalid_settings_are_rejected(key, value):
    with pytest.raises(SettingsError):
        _coerce(key, value)


def test_valid_settings_are_coerced():
    assert _coerce("crowd_threshold", "8") == 8
    assert _coerce("night_start", "19:15") == "19:15"
    assert _coerce("time_zone", "Europe/London") == "Europe/London"


@pytest.mark.parametrize("label", ["Glock 19", "Colt M1911", "Smith & Wesson Model 10", "Beretta M9", "SIG Sauer P320", "AK-47", "AR-15", "M4A1", "Ruger 10/22", "Winchester Model 70", "Remington 870", "Mossberg 500", "Benelli M4", "scissors", "bomb", "talwar", "katta", "straight_razor", "ustara"])
def test_requested_weapon_labels_map_when_a_trained_model_emits_them(label):
    from sentinel.detection import category_for
    assert category_for(label) == "weapon"


@pytest.mark.parametrize("label", ["stick", "wooden_stick", "rod", "metal rod", "ruler", "hammer", "screwdriver"])
def test_tools_can_be_drawn_without_automatically_triggering_weapon_alert(label):
    import numpy as np
    from sentinel.detection import category_for, annotate
    assert category_for(label) == "tool"
    detections = [Detection((0, 0, 10, 10), label, .95, "tool")]
    engine = RiskEngine()
    for t in (1000, 1001, 1002):
        assert run(engine, detections, t=t).level == "LOW"
    assert annotate(np.zeros((40, 40, 3), dtype=np.uint8), detections).shape == (40, 40, 3)
