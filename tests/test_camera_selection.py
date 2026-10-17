"""Named USB camera selection, unplugging, and safe switching; no real camera is opened."""
import sys
import time
from types import SimpleNamespace

import numpy as np
import pytest

from sentinel import camera as mod

FRAME = np.zeros((24, 32, 3), dtype=np.uint8)
DEVICES = [{"index": 0, "id": "usb-logitech", "name": "C270 HD WEBCAM"},
           {"index": 1, "id": "builtin", "name": "MacBook Air Camera"}]

class Capture:
    released = False
    def read(self):
        time.sleep(.005)
        return True, FRAME.copy()
    def release(self):
        self.released = True

@pytest.fixture
def camera(monkeypatch):
    monkeypatch.delenv("SENTINEL_VIDEO", raising=False)
    monkeypatch.setattr(mod, "camera_devices", lambda: (DEVICES, ""))
    cam = mod.Camera()
    yield cam
    cam.stop()

def test_mac_names_follow_opencv_unique_id_order(monkeypatch):
    class Device:
        def __init__(self, uid, name): self.uid, self.name = uid, name
        def uniqueID(self): return self.uid
        def localizedName(self): return self.name
    class Discovery:
        @staticmethod
        def devicesWithMediaType_(media):
            return [Device("B", "Built-in"), Device("A", "Logitech")] if media == "vide" else [Device("C", "Muxed")]
    monkeypatch.setitem(sys.modules, "objc", SimpleNamespace(loadBundle=lambda *a, **kw: None, lookUpClass=lambda _: Discovery))
    assert [(d["index"], d["name"]) for d in mod._mac_devices()] == [(0, "Logitech"), (1, "Built-in"), (2, "Muxed")]

def test_list_does_not_open_devices(camera, monkeypatch):
    monkeypatch.setattr(mod, "_open", lambda _: pytest.fail("Listing must not open a camera"))
    assert camera.devices()["cameras"] == DEVICES
    assert not camera.running

def test_explicit_selection_never_falls_back(camera, monkeypatch):
    opened = []
    monkeypatch.setattr(mod, "_open", lambda i: (opened.append(i) or None, None))
    assert not camera.start(0, "usb-logitech")[0]
    assert opened == [0] and not camera.running

def test_switch_opens_requested_camera_and_releases_old(camera, monkeypatch):
    captures = [Capture(), Capture()]
    monkeypatch.setattr(mod, "_open", lambda i: (captures[i], FRAME))
    assert camera.start(1, "builtin")[0]
    assert camera.start(0, "usb-logitech")[0]
    assert camera.running and camera.index == 0 and camera.name == "C270 HD WEBCAM"
    assert captures[1].released and not captures[0].released

def test_failed_switch_keeps_working_camera(camera, monkeypatch):
    cap = Capture()
    monkeypatch.setattr(mod, "_open", lambda i: (cap, FRAME) if i == 1 else (None, None))
    assert camera.start(1, "builtin")[0]
    assert not camera.start(0, "usb-logitech")[0]
    assert camera.running and camera.index == 1 and not cap.released
    assert camera.latest()[1] is not None

def test_unplugged_id_never_opens_another_camera(camera, monkeypatch):
    camera.device_id = "unplugged-logitech"
    monkeypatch.setattr(mod, "_open", lambda _: pytest.fail("Must not open a different camera"))
    assert not camera.start()[0]

def test_id_resolves_again_if_indices_change(camera, monkeypatch):
    monkeypatch.setattr(mod, "camera_devices", lambda: ([dict(DEVICES[0], index=1), dict(DEVICES[1], index=0)], ""))
    opened = []
    def open_capture(i):
        opened.append(i)
        return Capture(), FRAME
    monkeypatch.setattr(mod, "_open", open_capture)
    assert camera.start(0, "usb-logitech")[0]
    assert opened == [1] and camera.index == 1

def test_demo_cannot_masquerade_as_selected_webcam(camera, monkeypatch):
    monkeypatch.setenv("SENTINEL_VIDEO", "/tmp/example.mp4")
    assert camera.devices()["demo"]
    assert not camera.devices()["cameras"]
    assert not camera.start(0, "usb-logitech")[0]

def test_camera_api_lists_and_persists_named_selection(client, service, camera, monkeypatch):
    import sentinel.server as server
    service.camera = camera
    monkeypatch.setattr(server, "sentinel", service)
    monkeypatch.setattr(mod, "_open", lambda _: (Capture(), FRAME))
    assert client.get("/api/cameras").json()["cameras"][0]["name"] == "C270 HD WEBCAM"
    response = client.post("/api/camera/start", json={"index": 0, "device_id": "usb-logitech"})
    assert response.status_code == 200
    assert service.store.settings()["camera_device_id"] == "usb-logitech"
    assert client.get("/api/state").json()["camera"]["name"] == "C270 HD WEBCAM"
    assert client.post("/api/camera/start", json={"index": 0, "device_id": "unplugged"}).status_code == 409
    assert camera.running and camera.name == "C270 HD WEBCAM"

def test_numeric_setting_clears_previous_device_identity(service):
    service.update_settings({"camera_index": 0, "camera_device_id": "old-device"})
    service.camera.running = False
    service.update_settings({"camera_index": 1})
    assert service.store.settings()["camera_device_id"] == ""
    assert service.camera.device_id == ""
