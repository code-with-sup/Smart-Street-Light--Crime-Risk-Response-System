"""Activity heatmap: feet positions counted on a grid, saved per day, summed over a range."""

import time

import numpy as np

from sentinel.detection import Detection
from sentinel.service import HEAT_H, HEAT_W

FRAME = np.zeros((720, 1280, 3), np.uint8)


def person_with_feet_at(fx, fy):
    x, y = int(fx * 1280), int(fy * 720)
    return Detection((x - 30, y - 200, x + 30, y), "person", 0.9, "person", 1)


def test_feet_positions_are_counted_and_saved(service):
    now = time.time()
    service._heat_flushed = service._heat_bg_at = now  # no automatic flush / background mid-test
    before = service.heatmap(1)["cells"]  # other tests share this temporary database
    for i in range(5):
        service._add_heat([person_with_feet_at(0.25, 0.9)], FRAME, now + i)
    service._add_heat([Detection((0, 0, 50, 50), "car", 0.9, "vehicle")], FRAME, now + 6)  # cars don't count
    service._flush_heat()
    added = [a - b for a, b in zip(service.heatmap(1)["cells"], before, strict=True)]
    cell = int(0.9 * HEAT_H) * HEAT_W + int(0.25 * HEAT_W)
    assert added[cell] == 5 and sum(added) == 5


def test_days_add_up(service):
    service.store.add_heat("2099-01-01", [1] * (HEAT_W * HEAT_H))
    service.store.add_heat("2099-01-01", [2] * (HEAT_W * HEAT_H))
    assert service.store.heat_since("2099-01-01") == [[3] * (HEAT_W * HEAT_H)]


def test_background_picture_is_saved_with_faces_blurred(service, monkeypatch):
    from sentinel import service as service_module

    blurred = []
    monkeypatch.setattr(service_module, "blur_faces", lambda frame, dets: blurred.append(len(dets)) or frame)
    service._heat_bg_at = 0
    service._add_heat([person_with_feet_at(0.5, 0.5)], FRAME, time.time())
    assert blurred == [1] and service.heatmap(1)["background"].startswith("/evidence/heatmap_background.jpg")
