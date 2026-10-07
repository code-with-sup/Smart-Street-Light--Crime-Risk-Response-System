import os
import tempfile

# Keep tests away from the real incident database and evidence folder.
os.environ.setdefault("SENTINEL_DATA_DIR", tempfile.mkdtemp(prefix="sentinel-test-"))


# ----------------------------------------------------------------- shared fakes and fixtures

import numpy as np
import pytest
from fastapi.testclient import TestClient

from sentinel.config import DEFAULT_SETTINGS
from sentinel.service import Sentinel

FRAME = np.zeros((48, 64, 3), dtype=np.uint8)


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


@pytest.fixture
def client():
    from sentinel.server import app
    return TestClient(app)  # no context manager: the background service is not started


