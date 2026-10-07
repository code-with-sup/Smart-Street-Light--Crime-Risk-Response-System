"""Camera tamper detection on synthetic scenes, including the cases that must NOT alarm."""

import cv2
import numpy as np

from sentinel.tamper import TamperMonitor

RNG = np.random.default_rng(3)


def street(seed=3):
    """A detailed 'street' picture: random blocks plus edges."""
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (36, 64, 3), dtype=np.uint8)
    img = cv2.resize(img, (640, 360), interpolation=cv2.INTER_NEAREST)
    cv2.line(img, (0, 300), (640, 250), (255, 255, 255), 4)
    return img


def run(frames, start=1000.0, step=0.25):
    monitor, events = TamperMonitor(), []
    for i, frame in enumerate(frames):
        events = monitor.update(frame, start + i * step)
    return {e.kind for e in events}, monitor


def test_normal_static_scene_is_ok():
    kinds, monitor = run([street()] * 60)
    assert not kinds and monitor.status == "ok"


def test_hand_over_lens_is_covered_high():
    dark = np.full((360, 640, 3), 12, np.uint8)
    kinds, _ = run([street()] * 20 + [dark] * 12)
    assert "tamper_covered" in kinds


def test_slow_dusk_is_not_covered():
    base = street().astype(np.float32)
    frames = [np.clip(base * (1 - i / 260), 0, 255).astype(np.uint8) for i in range(240)]  # fades to ~8 % over a minute
    kinds, _ = run(frames)
    assert "tamper_covered" not in kinds


def test_smeared_lens_is_blurred():
    smeared = cv2.GaussianBlur(street(), (0, 0), 6)
    kinds, _ = run([street()] * 20 + [smeared] * 20)
    assert "tamper_blurred" in kinds


def test_heavily_sprayed_lens_still_raises_a_tamper_alarm():
    sprayed = cv2.GaussianBlur(street(), (0, 0), 25)  # so blurred it is a flat grey: reads as covered
    kinds, _ = run([street()] * 20 + [sprayed] * 20)
    assert kinds & {"tamper_covered", "tamper_blurred"}


def test_camera_turned_away_is_moved_then_accepted():
    kinds, _ = run([street(3)] * 20 + [street(99)] * 24)
    assert "tamper_moved" in kinds
    kinds_later, _ = run([street(3)] * 20 + [street(99)] * 120)  # 30 s later the new view is the normal
    assert "tamper_moved" not in kinds_later


def test_person_walking_past_is_not_moved():
    frames = []
    for i in range(60):
        f = street().copy()
        x = 40 + i * 8
        cv2.rectangle(f, (x, 120), (x + 60, 330), (30, 30, 30), -1)  # a figure crossing the view
        frames.append(f)
    kinds, _ = run(frames)
    assert "tamper_moved" not in kinds
