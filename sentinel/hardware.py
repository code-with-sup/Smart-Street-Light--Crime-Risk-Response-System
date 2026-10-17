"""ESP32 street-light link over USB serial, with a simulator when no board is connected.

Line protocol at 115200 baud (see firmware/esp32_street_light/esp32_street_light.ino):
  PC  -> ESP32   SET <brightness 0-100> <buzzer 0|1> <strobe 0|1>
                 CFG <ldr dark threshold 0-4095> <standalone dim % 0-100>
                 MOTION <enabled 0|1>
                 PING
  ESP32 -> PC    STATE <pir 0|1> <ldr 0-4095> <brightness> <buzzer> <strobe>   (every 500 ms)
                 SOS                      (the SOS button on the pole was pressed)
                 READY <firmware name>
                 PONG
If the ESP32 hears nothing for 5 s it falls back to local PIR + LDR lighting on its own, using the
threshold and dim level last sent with CFG, so the lamp behaves the same with or without the PC.
PIR motion only requests dim lighting; it does not activate the buzzer.
MOTION pauses PIR response independently of camera alarms. Manual tests temporarily pause PIR. If the USB link drops, the reader keeps
retrying the same port until it comes back.
"""

from __future__ import annotations

import contextlib
import logging
import os
import random
import subprocess
import sys
import threading
import time

log = logging.getLogger("sentinel.hardware")

BAUD = 115200
HEARTBEAT_SECONDS = 1.0
ONLINE_WINDOW_SECONDS = 3.0
PIR_BURST_SECONDS = 3.0
PIR_COOLDOWN_SECONDS = 10.0
RECONNECT_SECONDS = 3.0
BUZZER_MIN_SECONDS = 3.0


def list_ports() -> list[dict]:
    try:
        from serial.tools import list_ports as lp
    except ImportError:
        return []
    ports = []
    for port in lp.comports():
        name = port.device.lower()
        if "bluetooth" in name or "debug-console" in name or (port.vid is None and "usb" not in name):
            continue  # Bluetooth audio devices and system consoles show up as serial ports on macOS
        text = f"{port.description or ''} {port.manufacturer or ''}".lower()
        likely = any(word in text for word in ("cp210", "ch340", "ch910", "usb", "uart", "esp", "silicon labs"))
        ports.append({"device": port.device, "description": port.description or port.device, "likely_esp32": likely})
    return sorted(ports, key=lambda p: not p["likely_esp32"])


class HardwareLink:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._serial = None
        self._reader: threading.Thread | None = None
        self.mode = "simulator"
        self.port = ""
        self.firmware = ""
        self.error = ""
        self.pir = False
        self.pir_enabled = False
        self.pir_alarm = False
        self._motion_cfg_sent: bool | None = None
        self._sim_previous_motion = False
        self._sim_burst_until = 0.0
        self._sim_next_burst = 0.0
        self.ldr: int | None = None
        self.brightness = 0  # what the light is doing (reported by board, or simulated)
        self.buzzer = False
        self.strobe = False
        self._sos_pending = False
        self.last_sos = 0.0
        self.last_seen = 0.0
        self._sent: tuple[int, bool, bool] | None = None
        self._sent_at = 0.0
        self._buzzer_until = 0.0
        self._override: tuple[int, bool, float] | None = None
        self._cfg: tuple[int, int] | None = None
        self._cfg_sent: tuple[int, int] | None = None
        self._want_port = ""  # port the reader should keep (re)connected to; "" = stop

    # ------------------------------------------------------------ connect
    def connect(self, port: str) -> tuple[bool, str]:
        if not port:
            self.disconnect()
            return True, "Simulator mode"
        try:
            handle = self._open(port)
        except Exception as error:
            # keep whatever link is working now; only report the failed attempt
            return False, f"Could not open {port}: {error}"
        self.disconnect()
        self._serial = handle
        self.mode, self.port, self.error, self.firmware = "serial", port, "", ""
        self._sent = self._cfg_sent = self._motion_cfg_sent = None
        self._want_port = port
        self._reader = threading.Thread(target=self._read_loop, args=(port,), name="esp32-reader", daemon=True)
        self._reader.start()
        return True, f"Opened {port}. Waiting for the ESP32 to report…"

    @staticmethod
    def _open(port: str):
        import serial
        return serial.Serial(port, BAUD, timeout=0.5)

    def disconnect(self) -> None:
        self._want_port = ""
        handle, self._serial = self._serial, None
        if handle is not None:
            with contextlib.suppress(Exception):
                handle.close()
        if self._reader and self._reader.is_alive():
            self._reader.join(timeout=1)
        self._reader = None
        self.mode, self.port, self.last_seen, self.ldr = "simulator", "", 0.0, None

    @property
    def online(self) -> bool:
        if self.mode == "simulator":
            return True
        return time.time() - self.last_seen < ONLINE_WINDOW_SECONDS

    def _read_loop(self, port: str) -> None:
        while self._want_port == port:
            handle = self._serial
            if handle is None:  # link lost: retry the same port (cable re-plugged, board reset)
                time.sleep(RECONNECT_SECONDS)
                if self._want_port != port:
                    break
                try:
                    self._serial = self._open(port)
                    self._sent = self._cfg_sent = self._motion_cfg_sent = None
                    self.error = ""
                    log.info("reconnected to %s", port)
                except Exception:
                    pass
                continue
            try:
                raw = handle.readline()
            except Exception as error:
                if self._want_port != port:
                    break  # closed on purpose by disconnect()
                self.error = f"Serial link lost ({error}); retrying every {RECONNECT_SECONDS:.0f} s"
                log.warning(self.error)
                with contextlib.suppress(Exception):
                    handle.close()
                if self._serial is handle:
                    self._serial = None
                continue
            if raw:
                self._handle_line(raw.decode("utf-8", "replace").strip())

    def _handle_line(self, line: str) -> None:
        parts = line.split()
        if not parts:
            return
        if parts[0] == "STATE" and len(parts) >= 5:
            try:
                self.pir = parts[1] == "1"
                ldr = int(parts[2])
                self.ldr = None if ldr < 0 else ldr
                self.brightness = int(parts[3])
                self.buzzer = parts[4] == "1"
                self.strobe = len(parts) >= 6 and parts[5] == "1"
                self.pir_alarm = len(parts) >= 8 and parts[7] == "1"
                self.last_seen = time.time()
            except ValueError:
                pass
        elif parts[0] == "READY":
            self.firmware = " ".join(parts[1:])
            self.last_seen = time.time()
            self._sent = self._cfg_sent = self._motion_cfg_sent = None  # board rebooted: resend config and the current command
        elif parts[0] == "PONG":
            self.last_seen = time.time()
        elif parts[0] == "SOS":
            self.press_sos()

    # ---------------------------------------------------------------- SOS
    def press_sos(self) -> None:
        """The SOS button on the pole (or the dashboard's simulate button) was pressed."""
        self._sos_pending = True
        self.last_sos = time.time()

    def take_sos(self) -> bool:
        """True once per press; the service turns it into a HIGH incident."""
        pending, self._sos_pending = self._sos_pending, False
        return pending

    # ------------------------------------------------------------- output
    def test_output(self, brightness: int, buzzer: bool, seconds: float) -> None:
        """Manual test from the dashboard; overrides the risk engine briefly."""
        dur = max(BUZZER_MIN_SECONDS if buzzer else 0.5, min(seconds, 30))
        self._override = (max(0, min(100, brightness)), buzzer, time.time() + dur)
        if buzzer:
            self._buzzer_until = time.monotonic() + BUZZER_MIN_SECONDS

    def clear_test(self) -> None:
        self._override = None
        self._buzzer_until = 0.0

    def configure(self, ldr_dark_threshold: int, standalone_dim: int, *, pir_enabled: bool = False) -> None:
        """Settings the ESP32 uses on its own when the PC link is down."""
        self._cfg = (int(ldr_dark_threshold), int(standalone_dim))
        self.set_pir_enabled(pir_enabled)

    def set_pir_enabled(self, enabled: bool) -> None:
        if self.pir_enabled == enabled:
            return
        self.pir_enabled = enabled
        self.pir_alarm = False
        self._sim_previous_motion = self.pir
        self._sim_burst_until = 0.0
        self._motion_cfg_sent = None
        if self.mode == "serial":
            wanted = enabled and not self.override_active
            self._write(f"MOTION {int(wanted)}")
            self._motion_cfg_sent = wanted

    @property
    def override_active(self) -> bool:
        return self._override is not None and time.time() < self._override[2]

    def drive(self, brightness: int, buzzer: bool, *, people: int, is_night_clock: bool, strobe: bool = False) -> None:
        """Called by the service every loop with the risk engine's wanted output."""
        if self.mode == "simulator":
            self.pir = people > 0
        manual = self.override_active
        motion_enabled = self.pir_enabled and not manual
        if manual:
            brightness, buzzer, strobe = self._override[0], self._override[1], False
        else:
            self._override = None

        now_m = time.monotonic()
        if buzzer:
            if self._buzzer_until < now_m:
                self._buzzer_until = now_m + BUZZER_MIN_SECONDS
        buzzer = buzzer or (now_m < self._buzzer_until)

        if self.mode == "simulator":
            if not motion_enabled:
                self._sim_burst_until = 0.0
            elif self.pir and not self._sim_previous_motion and now_m >= self._sim_next_burst:
                self._sim_burst_until = now_m + PIR_BURST_SECONDS
                self._sim_next_burst = now_m + PIR_COOLDOWN_SECONDS
            if not self.pir:
                self._sim_burst_until = 0.0
            self._sim_previous_motion = self.pir
            self.pir_alarm = False  # PIR motion does not trigger buzzer alarm
            self.brightness, self.buzzer, self.strobe = brightness, buzzer, strobe
            base = 650 if is_night_clock else 3200
            self.ldr = max(0, min(4095, base + random.randint(-60, 60)))
            self.last_seen = time.time()
            return

        if motion_enabled != self._motion_cfg_sent:
            self._write(f"MOTION {int(motion_enabled)}")
            self._motion_cfg_sent = motion_enabled
        if self._cfg is not None and self._cfg != self._cfg_sent:
            self._write(f"CFG {self._cfg[0]} {self._cfg[1]}")
            self._cfg_sent = self._cfg
        wanted = (brightness, buzzer, strobe)
        now = time.time()
        if wanted != self._sent or now - self._sent_at >= HEARTBEAT_SECONDS:
            if not self.firmware:
                self._write("PING")
            self._write(f"SET {brightness} {int(buzzer)} {int(strobe)}")
            self._sent, self._sent_at = wanted, now
        self.brightness, self.buzzer, self.strobe = brightness, buzzer, strobe

    def _write(self, command: str) -> None:
        handle = self._serial
        if handle is None:
            return
        try:
            with self._lock:
                handle.write((command + "\n").encode())
        except Exception as error:
            self.error = f"Write failed: {error}"

    def readings(self) -> dict:
        return {
            "mode": self.mode, "port": self.port, "online": self.online, "firmware": self.firmware,
            "error": self.error, "pir": self.pir, "pir_enabled": self.pir_enabled, "pir_alarm": self.pir_alarm, "ldr": self.ldr, "brightness": self.brightness,
            "buzzer": self.buzzer, "strobe": self.strobe, "last_seen": self.last_seen, "override": self.override_active,
        }
