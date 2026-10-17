"""No camera, board, or outgoing alerts: exercise the alarm protocol and pause control."""
import shutil
import subprocess
from pathlib import Path

import pytest

from sentinel.detection import Detection
from sentinel.hardware import HardwareLink
from sentinel.service import SettingsError, _coerce


class SerialCapture:
    def __init__(self): self.commands = []
    def write(self, payload): self.commands.append(payload.decode().strip())


def attach_reported_board(service):
    link, capture = HardwareLink(), SerialCapture()
    link.mode, link._serial = "serial", capture
    link._handle_line("READY smart-street-esp32 v6")
    link._handle_line("STATE 0 -1 20 0 0 0 0")
    service.hardware = link
    return link, capture


@pytest.mark.parametrize("label,category", [("knife", "weapon"), ("fight", "event")])
def test_confirmed_detection_still_alarms_when_pir_paused(service, label, category):
    link, capture = attach_reported_board(service)
    service.update_settings({"pir_enabled": False})
    service.detector.output = [Detection((0, 0, 20, 20), label, .95, category)]
    last = service._tick(0)
    assert not service.result.buzzer
    service._tick(last)
    assert service.result.level == "HIGH" and service.result.brightness == 100
    assert service.result.buzzer and not link.pir_enabled
    assert capture.commands[-1].split()[:3] == ["SET", "100", "1"]
    assert "MOTION 0" in capture.commands
    assert not service.notifier.sent


@pytest.mark.parametrize("night", [False, True])
def test_host_does_not_latch_pir_buzzer_past_board_limit(service, monkeypatch, night):
    link, capture = attach_reported_board(service)
    service.camera.running = False
    service.update_settings({"pir_enabled": True})
    monkeypatch.setattr(service, "_night", lambda: (night, "clock"))
    link._handle_line("STATE 1 -1 100 1 0 1 1")
    service._tick(0)
    assert link.pir_alarm and service.result.level != "HIGH"
    assert capture.commands[-1] == "SET 0 0 0"
    link._handle_line("STATE 1 -1 100 0 0 1 0")
    service._tick(0)
    assert link.pir and not link.pir_alarm and not link.buzzer
    assert capture.commands[-1].split()[2] == "0"
    assert not service.notifier.sent


def test_pir_pause_persists_and_ignores_motion_for_risk(service, monkeypatch):
    link, capture = attach_reported_board(service)
    service.update_settings({"pir_enabled": True})
    service.update_settings({"pir_enabled": False})
    assert service.store.settings()["pir_enabled"] is False
    assert capture.commands[-1] == "MOTION 0"
    link._handle_line("STATE 1 -1 0 0 0 0 0")
    service.camera.running = False
    monkeypatch.setattr(service, "_night", lambda: (True, "clock"))
    service._tick(0)
    assert service.result.level == "LOW" and not service.result.buzzer
    assert link.readings()["pir_enabled"] is False
    assert not service.notifier.sent


def test_manual_tests_temporarily_pause_pir(service):
    link, capture = attach_reported_board(service)
    link.set_pir_enabled(True)
    link.test_output(0, False, 5)
    link.drive(100, True, people=0, is_night_clock=False)
    assert "MOTION 0" in capture.commands
    assert capture.commands[-1] == "SET 0 0 0"
    link.clear_test()
    link.drive(0, False, people=0, is_night_clock=False)
    assert capture.commands[-1] == "MOTION 1"
    assert [c for c in capture.commands if c.startswith("SET ")][-1] == "SET 0 0 0"


def test_simulated_held_motion_dims_light_without_buzzer(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("sentinel.hardware.time.monotonic", lambda: clock[0])
    link = HardwareLink()
    link.set_pir_enabled(True)
    link.drive(20, False, people=1, is_night_clock=False)
    assert link.pir and not link.buzzer and link.brightness == 20
    for now in [103.0, 110.0, 120.0]:
        clock[0] = now
        link.drive(20, False, people=1, is_night_clock=False)
        assert link.pir and not link.buzzer and link.brightness == 20
    link.drive(0, False, people=0, is_night_clock=False)
    assert link.brightness == 0
    clock[0] = 121.0
    link.drive(20, False, people=1, is_night_clock=False)
    assert link.pir and not link.buzzer and link.brightness == 20
    link.set_pir_enabled(False)
    link.drive(0, False, people=1, is_night_clock=False)
    assert not link.buzzer and link.brightness == 0


@pytest.mark.parametrize("value", ["false", 0, None])
def test_pir_enable_requires_boolean(value):
    with pytest.raises(SettingsError): _coerce("pir_enabled", value)


def test_settings_api_can_pause_only_pir(client, service, monkeypatch):
    import sentinel.server as server
    monkeypatch.setattr(server, "sentinel", service)
    response = client.put("/api/settings", json={"pir_enabled": False})
    assert response.status_code == 200 and response.json()["pir_enabled"] is False
    assert service.camera.running  # pausing PIR does not stop a camera


def test_board_motion_timer_and_chirp_boundaries(tmp_path):
    compiler = shutil.which("c++")
    if not compiler: pytest.skip("C++ compiler unavailable")
    firmware = Path(__file__).resolve().parents[1] / "firmware/esp32_street_light"
    source = tmp_path / "check.cpp"
    source.write_text(r'''#include <cassert>
#include "motion_alarm.h"
int main() {
  MotionAlarm a;
  a.update(false,true,0); a.update(true,true,1); assert(a.active());
  a.update(true,true,3000); assert(a.active());
  a.update(true,true,3001); assert(!a.active());
  a.update(true,true,60000); assert(!a.active()); // held HIGH never repeats
  a.update(false,true,60001); a.update(true,true,60002); assert(a.active());
  a.update(true,false,60003); assert(!a.active()); // pause is immediate
  a.update(true,true,80000); assert(!a.active()); // enable while HIGH stays quiet
  a.update(false,true,80001); a.update(true,true,80002); assert(a.active());
  MotionAlarm cooldown;
  cooldown.update(true,true,1); cooldown.update(false,true,50);
  cooldown.update(true,true,100); assert(!cooldown.active());
  cooldown.update(true,true,20000); assert(!cooldown.active());
  cooldown.update(false,true,20001); cooldown.update(true,true,20002); assert(cooldown.active());
  MotionAlarm wrapped;
  wrapped.update(true,true,UINT32_MAX-999);
  wrapped.update(true,true,1999); assert(wrapped.active());
  wrapped.update(true,true,2000); assert(!wrapped.active());
  QuietChirp q;
  assert(q.output(true,100)); assert(q.output(true,159));
  assert(!q.output(true,160)); assert(!q.output(true,849));
  assert(q.output(true,850)); assert(!q.output(false,851));
}
''')
    binary = tmp_path / "check"
    subprocess.run([compiler, "-std=c++17", "-I", str(firmware), str(source), "-o", str(binary)], check=True, capture_output=True, text=True)
    subprocess.run([str(binary)], check=True, capture_output=True, text=True)
