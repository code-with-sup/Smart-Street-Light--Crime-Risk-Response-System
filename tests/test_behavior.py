"""Crime-behaviour rules (synthetic poses) and how events drive the risk level."""

import numpy as np
import pytest

from sentinel.behavior import BehaviorAnalyzer, Event
from sentinel.config import DEFAULT_SETTINGS
from sentinel.detection import Detection, category_for
from sentinel.risk import RiskEngine

SETTINGS = dict(DEFAULT_SETTINGS)


def pose(cx, top, height, *, lying=False, hands_up=False, wrist_dx=0.0):
    """17 COCO keypoints for a simple figure; coordinates in pixels, confidence 0.9."""
    k = np.zeros((17, 3))
    k[:, 2] = 0.9
    if lying:  # body along x at ground level
        y = top + height * 0.8
        k[0] = (cx - height * 0.45, y, 0.9)
        k[5], k[6] = (cx - height * 0.3, y - 5, 0.9), (cx - height * 0.3, y + 5, 0.9)
        k[11], k[12] = (cx + height * 0.05, y - 5, 0.9), (cx + height * 0.05, y + 5, 0.9)
        k[9], k[10] = (cx - height * 0.2, y, 0.9), (cx - height * 0.2, y + 8, 0.9)
        return k
    k[0] = (cx, top + height * 0.08, 0.9)
    k[5], k[6] = (cx - 15, top + height * 0.2, 0.9), (cx + 15, top + height * 0.2, 0.9)
    k[11], k[12] = (cx - 12, top + height * 0.52, 0.9), (cx + 12, top + height * 0.52, 0.9)
    wrist_y = top - 10 if hands_up else top + height * 0.5
    k[9], k[10] = (cx - 25 + wrist_dx, wrist_y, 0.9), (cx + 25 + wrist_dx, wrist_y, 0.9)
    return k


def person(track_id, cx, top=100, height=200, **pose_kwargs):
    lying = pose_kwargs.get("lying")
    box = (cx - 130, top + 120, cx + 130, top + 200) if lying else (cx - 40, top, cx + 40, top + height)
    return Detection(box, "person", 0.9, "person", track_id, pose(cx, top, height, **pose_kwargs))


def run(frames, start=1000.0, step=0.25):
    analyzer, events = BehaviorAnalyzer(), []
    for i, dets in enumerate(frames):
        events = analyzer.update(dets, start + i * step)
    return events


def kinds(events):
    return {e.kind for e in events}


def test_person_lying_down_for_two_seconds_is_person_down():
    assert "person_down" in kinds(run([[person(1, 300, lying=True)]] * 12))


def test_brief_crouch_is_not_person_down():
    frames = [[person(1, 300, lying=True)]] * 3 + [[person(1, 300)]] * 9
    assert "person_down" not in kinds(run(frames))


def test_hands_up_near_another_person_is_possible_robbery():
    frames = [[person(1, 300, hands_up=True), person(2, 420)]] * 10
    events = run(frames)
    assert "hands_up" in kinds(events)
    assert next(e for e in events if e.kind == "hands_up").severity == "HIGH"


def test_hands_up_alone_is_ignored():
    assert "hands_up" not in kinds(run([[person(1, 300, hands_up=True)]] * 10))


def test_close_people_with_fast_arms_is_possible_fight():
    frames = [[person(1, 300, wrist_dx=(60 if i % 2 else -60)), person(2, 360, wrist_dx=(-60 if i % 2 else 60))]
              for i in range(8)]
    assert "fight" in kinds(run(frames))


def test_two_people_standing_close_is_not_a_fight():
    assert "fight" not in kinds(run([[person(1, 300), person(2, 360)]] * 8))


def test_several_people_running_is_medium_event():
    frames = [[person(1, 100 + i * 120), person(2, 600 + i * 120)] for i in range(8)]
    events = run(frames)
    assert "running" in kinds(events)
    assert next(e for e in events if e.kind == "running").severity == "MEDIUM"


def test_one_jogger_is_not_an_event():
    assert "running" not in kinds(run([[person(1, 100 + i * 120)] for i in range(8)]))


def test_high_event_raises_high_and_buzzer():
    engine = RiskEngine()
    event = Event("fight", "Possible fight", "HIGH", (1, 2), (0, 0, 10, 10), 0.6)
    result = engine.evaluate([], events=[event], is_night=False, motion=False, settings=SETTINGS, now=1000)
    assert (result.level, result.buzzer, result.threat_label) == ("HIGH", True, "Possible fight")


def test_custom_model_crime_class_needs_two_of_three_passes():
    engine = RiskEngine()
    fight = Detection((0, 0, 10, 10), "fight", 0.8, "event")
    assert engine.evaluate([fight], is_night=False, motion=False, settings=SETTINGS, now=1000).level != "HIGH"
    result = engine.evaluate([fight], is_night=False, motion=False, settings=SETTINGS, now=1001)
    assert result.level == "HIGH" and result.event.label == "Fight detected"


def test_custom_class_names_map_to_categories():
    assert category_for("weapon") == "weapon"
    assert category_for("pistol") == "weapon"
    assert category_for("submachine-gun") == "weapon"
    assert category_for("Fighting") == "event"
    assert category_for("person") is None
    assert category_for("Bat (Animal)") is None


@pytest.mark.parametrize("name,category", [  # the crime model's classes, names exactly as trained
    ("Violence", "event"), ("violent", "event"), ("fight", "event"), ("Robbery Using Gun", "event"),
    ("Gun", "weapon"), ("Man Holding Gun", "weapon"), ("knifes", "weapon"),
    ("No Fight", "calm"), ("Non-Violence", "calm"), ("Bystander", None),
])
def test_crime_model_classes(name, category):
    assert category_for(name) == category


def test_calm_detections_never_raise_risk():
    calm = Detection((0, 0, 100, 200), "No Fight", 0.95, "calm")
    engine = RiskEngine()
    for t in range(5):
        assert engine.evaluate([calm], is_night=False, motion=False, settings=SETTINGS, now=1000 + t).level == "LOW"


def test_seated_close_up_at_a_webcam_is_not_person_down():
    """Real false alarm: head and shoulders filling a 1920x1080 webcam frame, hips out of view.
    The box is wider than tall and touches the frame edges, which used to read as 'lying down'."""
    k = np.zeros((17, 3))
    k[0] = (960, 420, 0.95)                                        # nose
    k[5], k[6] = (700, 1000, 0.9), (1220, 1010, 0.9)               # shoulders at the bottom of the frame
    k[11], k[12] = (720, 1075, 0.2), (1200, 1075, 0.2)             # hips out of view (low confidence)
    me = Detection((200, 5, 1720, 1080), "person", 0.88, "person", 2, k)
    analyzer, events = BehaviorAnalyzer(), []
    for i in range(16):
        events = analyzer.update([me], 1000 + i * 0.25, (1920, 1080))
    assert "person_down" not in kinds(events)


def test_person_lying_in_full_view_is_still_detected_with_frame_size():
    analyzer, events = BehaviorAnalyzer(), []
    for i in range(12):
        events = analyzer.update([person(1, 600, top=500, lying=True)], 1000 + i * 0.25, (1920, 1080))
    assert "person_down" in kinds(events)
