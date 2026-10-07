"""ESP32 street-light link over USB serial, with a simulator when no board is connected.

Line protocol at 115200 baud (see firmware/esp32_street_light/esp32_street_light.ino):
  PC  -> ESP32   SET <brightness 0-100> <buzzer 0|1> <strobe 0|1>
                 CFG <ldr dark threshold 0-4095> <standalone dim % 0-100>
                 PING
  ESP32 -> PC    STATE <pir 0|1> <ldr 0-4095> <brightness> <buzzer> <strobe>   (every 500 ms)
                 SOS                      (the SOS button on the pole was pressed)
                 READY <firmware name>
                 PONG
If the ESP32 hears nothing for 5 s it falls back to local PIR + LDR lighting on its own, using the
threshold and dim level last sent with CFG, so the lamp behaves the same with or without the PC.
If the USB link drops, the reader keeps retrying the same port until it comes back.
"""

from __future__ import annotations

import contextlib
import logging
import random
import threading
import time

log = logging.getLogger("sentinel.hardware")

BAUD = 115200
HEARTBEAT_SECONDS = 1.0
ONLINE_WINDOW_SECONDS = 3.0
RECONNECT_SECONDS = 3.0


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
        self.ldr: int | None = None
        self.brightness = 0  # what the light is doing (reported by board, or simulated)
        self.buzzer = False
        self.strobe = False
        self._sos_pending = False
        self.last_sos = 0.0
        self.last_seen = 0.0
        self._sent: tuple[int, bool, bool] | None = None
        self._sent_at = 0.0
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
        self._sent = self._cfg_sent = None
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
                    self._sent = self._cfg_sent = None
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
                self.ldr = int(parts[2])
                self.brightness = int(parts[3])
                self.buzzer = parts[4] == "1"
                self.strobe = len(parts) >= 6 and parts[5] == "1"
                self.last_seen = time.time()
            except ValueError:
                pass
        elif parts[0] == "READY":
            self.firmware = " ".join(parts[1:])
            self.last_seen = time.time()
            self._sent = self._cfg_sent = None  # board rebooted: resend config and the current command
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
        self._override = (max(0, min(100, brightness)), buzzer, time.time() + max(0.5, min(seconds, 30)))

    def clear_test(self) -> None:
        self._override = None

    def configure(self, ldr_dark_threshold: int, standalone_dim: int) -> None:
        """Settings the ESP32 uses on its own when the PC link is down."""
        self._cfg = (int(ldr_dark_threshold), int(standalone_dim))

    @property
    def override_active(self) -> bool:
        return self._override is not None and time.time() < self._override[2]

    def drive(self, brightness: int, buzzer: bool, *, people: int, is_night_clock: bool, strobe: bool = False) -> None:
        """Called by the service every loop with the risk engine's wanted output."""
        if self.override_active:
            brightness, buzzer, strobe = self._override[0], self._override[1], False
        else:
            self._override = None
        if self.mode == "simulator":
            self.brightness, self.buzzer, self.strobe = brightness, buzzer, strobe
            self.pir = people > 0
            base = 650 if is_night_clock else 3200
            self.ldr = max(0, min(4095, base + random.randint(-60, 60)))
            self.last_seen = time.time()
            return
        if self._cfg is not None and self._cfg != self._cfg_sent:
            self._write(f"CFG {self._cfg[0]} {self._cfg[1]}")
            self._cfg_sent = self._cfg
        wanted = (brightness, buzzer, strobe)
        now = time.time()
        if wanted != self._sent or now - self._sent_at >= HEARTBEAT_SECONDS:
            self._write(f"SET {brightness} {int(buzzer)} {int(strobe)}")
            self._sent, self._sent_at = wanted, now

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
            "error": self.error, "pir": self.pir, "ldr": self.ldr, "brightness": self.brightness,
            "buzzer": self.buzzer, "strobe": self.strobe, "last_seen": self.last_seen, "override": self.override_active,
        }
