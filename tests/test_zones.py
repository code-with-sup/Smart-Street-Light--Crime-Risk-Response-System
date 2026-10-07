"""Zones and tripwires: entry, loitering, crossing direction, schedules, validation."""

import pytest

from sentinel.detection import Detection
from sentinel.zones import ZoneError, ZoneMonitor, validate_zone

FRAME = (1000, 1000)
AREA = validate_zone({"id": "atm", "name": "ATM", "type": "area", "rule": "no_entry", "level": "HIGH",
                      "points": [[0.6, 0.6], [0.9, 0.6], [0.9, 0.9], [0.6, 0.9]]})
LOITER = validate_zone({"id": "stop", "name": "Bus stop", "type": "area", "rule": "loiter", "seconds": 10,
                        "points": [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]]})
LINE = validate_zone({"id": "lane", "name": "Lane", "type": "line", "points": [[0.5, 0.0], [0.5, 1.0]]})


def person(track_id, fx, fy):
    """A person whose feet are at (fx, fy) in frame fractions."""
    x, y = fx * FRAME[0], fy * FRAME[1]
    return Detection((int(x - 40), int(y - 200), int(x + 40), int(y)), "person", 0.9, "person", track_id)


def kinds(events):
    return {e.kind for e in events}


def test_walking_into_a_no_entry_area_triggers_at_its_level():
    monitor = ZoneMonitor()
    assert not monitor.update([person(1, 0.3, 0.75)], [AREA], FRAME, 1000, False)
    events = monitor.update([person(1, 0.75, 0.75)], [AREA], FRAME, 1001, False)
    assert kinds(events) == {"zone_entry"} and events[0].severity == "HIGH" and "ATM" in events[0].label
    assert monitor.active == {"atm"}


def test_standing_in_front_of_an_area_does_not_count():
    # the body overlaps the zone but the feet are below it
    monitor = ZoneMonitor()
    assert not monitor.update([person(1, 0.75, 0.97)], [AREA], FRAME, 1000, False)


def test_loitering_only_after_the_set_time():
    monitor = ZoneMonitor()
    assert not monitor.update([person(2, 0.25, 0.3)], [LOITER], FRAME, 1000, False)
    assert not monitor.update([person(2, 0.25, 0.3)], [LOITER], FRAME, 1005, False)
    events = monitor.update([person(2, 0.25, 0.3)], [LOITER], FRAME, 1011, False)
    assert kinds(events) == {"zone_loiter"} and events[0].severity == "MEDIUM"


def test_leaving_resets_the_loiter_timer():
    monitor = ZoneMonitor()
    monitor.update([person(2, 0.25, 0.3)], [LOITER], FRAME, 1000, False)
    monitor.update([person(2, 0.8, 0.3)], [LOITER], FRAME, 1006, False)  # stepped out
    assert not monitor.update([person(2, 0.25, 0.3)], [LOITER], FRAME, 1012, False)


def test_crossing_a_tripwire_is_held_briefly():
    monitor = ZoneMonitor()
    monitor.update([person(3, 0.3, 0.5)], [LINE], FRAME, 1000, False)
    assert kinds(monitor.update([person(3, 0.7, 0.5)], [LINE], FRAME, 1001, False)) == {"line_cross"}
    assert kinds(monitor.update([], [LINE], FRAME, 1004, False)) == {"line_cross"}  # still held
    assert not monitor.update([], [LINE], FRAME, 1007, False)


def test_tripwire_direction_follows_the_dashboard_arrow():
    # line A (top) -> B (bottom): arrow = (dy, -dx) = (1, 0), i.e. pointing to the right of the screen
    with_arrow = validate_zone({**LINE, "direction": "a_to_b"})
    monitor = ZoneMonitor()
    monitor.update([person(4, 0.3, 0.5)], [with_arrow], FRAME, 1000, False)
    assert kinds(monitor.update([person(4, 0.7, 0.5)], [with_arrow], FRAME, 1001, False)) == {"line_cross"}
    monitor = ZoneMonitor()
    monitor.update([person(5, 0.7, 0.5)], [with_arrow], FRAME, 1000, False)
    assert not monitor.update([person(5, 0.3, 0.5)], [with_arrow], FRAME, 1001, False)  # against the arrow
    against = validate_zone({**LINE, "direction": "b_to_a"})
    monitor = ZoneMonitor()
    monitor.update([person(6, 0.7, 0.5)], [against], FRAME, 1000, False)
    assert kinds(monitor.update([person(6, 0.3, 0.5)], [against], FRAME, 1001, False)) == {"line_cross"}


def test_walking_alongside_a_tripwire_is_not_a_crossing():
    monitor = ZoneMonitor()
    monitor.update([person(6, 0.3, 0.2)], [LINE], FRAME, 1000, False)
    assert not monitor.update([person(6, 0.3, 0.8)], [LINE], FRAME, 1001, False)


def test_night_only_zone_is_ignored_by_day():
    night = validate_zone({**AREA, "schedule": "night"})
    monitor = ZoneMonitor()
    assert not monitor.update([person(1, 0.75, 0.75)], [night], FRAME, 1000, is_night=False)
    assert monitor.update([person(1, 0.75, 0.75)], [night], FRAME, 1001, is_night=True)


def test_disabled_zone_is_ignored():
    monitor = ZoneMonitor()
    assert not monitor.update([person(1, 0.75, 0.75)], [{**AREA, "enabled": False}], FRAME, 1000, False)


@pytest.mark.parametrize("raw", [
    {"type": "area", "points": [[0.1, 0.1], [0.2, 0.2]]},             # too few points
    {"type": "line", "points": [[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]]},  # a line has 2
    {"type": "area", "points": [[0, 0], [2, 0], [0, 1]]},             # outside the frame
    {"type": "circle", "points": [[0, 0], [1, 0], [0, 1]]},
    {"type": "area", "points": [[0, 0], [1, 0], [0, 1]], "level": "LOW"},
    {"type": "area", "points": [[0, 0], [1, 0], [0, 1]], "rule": "loiter", "seconds": 1},
])
def test_bad_zones_are_rejected(raw):
    with pytest.raises(ZoneError):
        validate_zone(raw)
