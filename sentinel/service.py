"""The Sentinel service: camera -> detection -> risk -> light/buzzer -> incidents -> alerts."""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from collections import Counter, deque
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import cv2

from .alerts import Notifier
from .behavior import BehaviorAnalyzer, Event
from .camera import Camera
from .clips import ClipRecorder
from .config import DEFAULT_SETTINGS, EVIDENCE_DIR
from .detection import MODELS, Detection, Detector, annotate
from .hardware import HardwareLink
from .risk import LEVELS, RiskEngine, RiskResult
from .storage import Store
from .privacy import MODES as BLUR_MODES
from .privacy import blur_faces
from .tamper import TamperMonitor
from .voice import MODES as VOICE_MODES
from .voice import Speaker
from .zones import ZoneMonitor, draw_zones, validate_zone

log = logging.getLogger("sentinel.service")

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
METRIC_INTERVAL = 15
HEAT_W, HEAT_H = 48, 27          # activity heatmap grid (16:9)
HEAT_BACKGROUND = "heatmap_background.jpg"
HEAT_BACKGROUND_EVERY = 600      # refresh the heatmap's background picture every 10 min
STALE_FRAME_SECONDS = 1.5  # camera "running" but no new frame for this long: treat the scene as empty
PURGE_INTERVAL = 6 * 3600
RANGES = {
    "confidence": (0.05, 0.95), "weapon_confidence": (0.05, 0.95), "detect_interval_ms": (50, 2000),
    "ldr_dark_threshold": (0, 4095), "crowd_threshold": (2, 100), "loiter_seconds": (5, 3600),
    "low_brightness": (0, 100), "alert_cooldown_s": (0, 3600), "incident_cooldown_s": (5, 3600),
    "evidence_retention_days": (1, 365), "camera_index": (0, 9), "sos_hold_s": (10, 600),
    "escalate_after_min": (0, 240), "lamp_watts": (1, 2000), "tariff_per_kwh": (0, 1000), "co2_kg_per_kwh": (0, 3),
}
CHOICES = {"alert_mode": ("manual", "auto"), "day_night_source": ("auto", "clock", "ldr"), "model": tuple(MODELS),
           "blur_faces": BLUR_MODES, "voice_warnings": VOICE_MODES}
VOICE_REPEAT_SECONDS = 30


class SettingsError(ValueError):
    pass


def _coerce(key: str, value):
    default = DEFAULT_SETTINGS[key]
    try:
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise ValueError  # "false" must not become True
        elif isinstance(default, int):
            if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
                raise ValueError
            value = int(value)
        elif isinstance(default, float):
            if isinstance(value, bool):
                raise ValueError
            value = float(value)
            if not math.isfinite(value):
                raise ValueError
        elif isinstance(default, str):
            value = str(value).strip()
    except (TypeError, ValueError):
        raise SettingsError(f"{key} has an invalid value") from None
    if key in RANGES:
        low, high = RANGES[key]
        if not low <= value <= high:
            raise SettingsError(f"{key} must be between {low} and {high}")
    if key in CHOICES and value not in CHOICES[key]:
        raise SettingsError(f"{key} must be one of {', '.join(CHOICES[key])}")
    if key in ("voice_high", "voice_medium", "voice_sos") and not 1 <= len(value) <= 200:
        raise SettingsError("Voice messages must be 1-200 characters")
    if key == "currency" and not 1 <= len(value) <= 4:
        raise SettingsError("currency must be 1-4 characters, e.g. ₹ or USD")
    if key in ("night_start", "night_end") and not TIME_RE.match(value):
        raise SettingsError(f"{key} must be HH:MM (24-hour)")
    if key == "time_zone":
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise SettingsError("Unknown time zone") from None
    return value


class Sentinel:
    def __init__(self) -> None:
        self.store = Store()
        self.settings = self.store.settings()
        self.camera = Camera()
        self.camera.index = self.settings["camera_index"]
        self.camera.mirror = self.settings["mirror"]
        self.detector: Detector | None = None
        self.detector_loading = True
        self.risk = RiskEngine()
        self.behavior = BehaviorAnalyzer()
        self.tamper = TamperMonitor()
        self.zone_monitor = ZoneMonitor()
        self.speaker = Speaker()
        self._last_spoken = (0.0, "")  # (time, level) of the last warning
        self.events: list[Event] = []
        self.result = RiskResult()
        self.hardware = HardwareLink()
        self.notifier = Notifier()
        self.detections: list[Detection] = []
        self.inference_ms = 0.0
        self.is_night = False
        self.night_source = "clock"
        self.activity: deque[dict] = deque(maxlen=40)
        self._activity_id = 0
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._det_version = 0
        self._jpeg: tuple[tuple[int, int], bytes] | None = None
        self._last_incident: dict[str, float] = {}
        self._last_auto_alert = 0.0
        self._last_metric = 0.0
        self._last_purge = 0.0
        self._today_cache: tuple[float, int] = (0.0, 0)
        self._reset_scene = False
        self._last_fresh = 0.0
        self.clips = ClipRecorder(EVIDENCE_DIR, self._clip_saved)
        self._energy = {"t": 0.0, "day": "", "lamp_wh": 0.0, "baseline_wh": 0.0, "night_s": 0.0, "flushed": 0.0}
        self._last_escalation_check = 0.0
        self._energy_today: tuple[float, dict] = (0.0, {})
        self._heat = [0] * (HEAT_W * HEAT_H)
        self._heat_day = ""
        self._heat_flushed = 0.0
        self._heat_bg_at = 0.0
        self._tamper_events: list[Event] = []
        self._sos_until = 0.0   # SOS keeps risk HIGH until this time (or an operator clears it)
        self._sos_new = False   # a press arrived this tick: always record an incident for it

    # ------------------------------------------------------------ lifecycle
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.settings["time_zone"])

    def start(self) -> None:
        self._running = True
        threading.Thread(target=self._load_detector, name="detector-load", daemon=True).start()
        if self.settings["serial_port"]:
            ok, message = self.hardware.connect(self.settings["serial_port"])
            self.note("system", message if ok else f"ESP32: {message}")
        self._thread = threading.Thread(target=self._loop, name="sentinel", daemon=True)
        self._thread.start()
        self.clips.start(self._clip_frame)
        self.note("system", "Sentinel started")

    def shutdown(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)  # so no tick can re-light the lamp after the "off" below
        self.clips.stop()
        self._flush_energy()
        self._flush_heat()
        self.camera.stop()
        self.hardware.clear_test()
        self.hardware.drive(0, False, people=0, is_night_clock=False)
        self.hardware.disconnect()
        self.notifier.shutdown()

    def _load_detector(self, model: str | None = None) -> None:
        model = model or self.settings["model"]
        self.detector_loading = True
        detector = Detector(model, behaviour=self.settings["behaviour_analysis"])
        if detector.ready or self.detector is None:
            self.detector = detector  # swap in one assignment; the loop picks it up on its next pass
        self.detector_loading = False
        if detector.ready:
            tracking = "tracking on" if detector.tracking else "tracking off"
            self.note("system", f"AI detector ready on {detector.device.upper()} ({', '.join(detector.models)}, {tracking})")
        else:
            self.note("system", detector.error + (" — keeping the previous model" if self.detector is not detector else ""))

    def change_model(self, model: str) -> None:
        threading.Thread(target=self._load_detector, args=(model,), name="detector-load", daemon=True).start()

    def _clip_frame(self):
        """Current camera frame with the latest boxes drawn, for the clip recorder (None when off)."""
        if not self.camera.running:
            return None
        _frame_id, frame = self.camera.latest()
        if frame is None:
            return None
        with self._lock:
            detections, events = list(self.detections), list(self.events)
        return self._overlay(frame, detections, events, evidence=True)

    def _clip_saved(self, incident_id: int, name: str) -> None:
        if self.store.incident(incident_id) is None:  # deleted while recording
            (EVIDENCE_DIR / name).unlink(missing_ok=True)
            return
        self.store.set_clip(incident_id, name)
        self.note("system", f"Video clip saved for incident #{incident_id}", incident_id=incident_id)

    def _voice(self, result: RiskResult, previous: str, *, sos: bool, now: float) -> None:
        """Speak when risk rises, then repeat every 30 s while it stays raised; SOS has its own message."""
        mode = self.settings["voice_warnings"]
        if mode == "off":
            return
        if sos:
            text = self.settings["voice_sos"]
        elif result.level == "HIGH" or (result.level == "MEDIUM" and mode == "medium"):
            text = self.settings["voice_high" if result.level == "HIGH" else "voice_medium"]
        else:
            return
        last_time, last_level = self._last_spoken
        rose = LEVELS.index(result.level) > LEVELS.index(previous)
        due = sos or rose or result.level != last_level or now - last_time >= VOICE_REPEAT_SECONDS
        if due and self.speaker.say(text):
            self._last_spoken = (now, result.level)

    def clear_sos(self) -> None:
        """Operator has responded: stop holding HIGH for the SOS (other threats still count)."""
        if self._sos_until:
            self._sos_until = 0.0
            self.note("alert", "SOS cleared by operator")

    def camera_changed(self) -> None:
        """New camera or video: start tracking and risk timers fresh."""
        self._reset_scene = True

    def note(self, kind: str, text: str, level: str | None = None, incident_id: int | None = None) -> None:
        with self._lock:
            self._activity_id += 1
            self.activity.appendleft({"id": self._activity_id, "ts": time.time(), "kind": kind, "text": text,
                                      "level": level, "incident_id": incident_id})

    # ----------------------------------------------------------- main loop
    def _loop(self) -> None:
        last_frame = 0
        while self._running:
            started = time.monotonic()
            try:
                last_frame = self._tick(last_frame)
            except Exception:
                log.exception("sentinel loop error")
            interval = self.settings["detect_interval_ms"] / 1000 if self.camera.running else 0.5
            time.sleep(max(0.02, interval - (time.monotonic() - started)))

    def _tick(self, last_frame: int) -> int:
        settings = self.settings
        self.is_night, self.night_source = self._night()
        motion = self.hardware.pir if self.hardware.mode == "serial" and self.hardware.online else False
        frame_id, frame = self.camera.latest()
        detector = self.detector
        if self._reset_scene:  # done on this thread so it never races the tracker mid-update
            self._reset_scene = False
            self.risk.reset()
            self.behavior.reset()
            self.tamper.reset()
            self.zone_monitor.reset()
            if detector and detector.ready:
                detector.reset_tracks()
        now = time.time()
        if self.hardware.take_sos():
            self._sos_until, self._sos_new = now + settings["sos_hold_s"], True
            self.note("alert", "SOS button pressed on the street light", "HIGH")
        if self.camera.running and frame is not None and detector and detector.ready:
            if frame_id != last_frame:
                began = time.perf_counter()
                detections = detector.detect(frame, settings["confidence"], settings["weapon_confidence"])
                self.inference_ms = (time.perf_counter() - began) * 1000
                self._add_heat(detections, frame, now)
                self._tamper_events = self.tamper.update(frame, now) if settings["tamper_detection"] else []
                last_frame, self._last_fresh = frame_id, now
            elif now - self._last_fresh > STALE_FRAME_SECONDS:
                detections, frame = [], None  # camera stalled: don't keep acting on an old frame
            elif self._sos_new:
                detections = list(self.detections)  # SOS can't wait for the next frame; reuse the last scene
            else:
                # loop is faster than the camera: no new evidence, but keep the lamp heartbeat
                # and housekeeping going (re-evaluating the same frame would double-count weapons)
                self._drive(self.result, self.detections)
                self._housekeeping(self.result, self.detections, now)
                return last_frame
        else:
            detections, frame = [], None
            if not self.camera.running and self.camera.error:
                self.note("system", self.camera.error)
                self.camera.error = ""

        events = self.behavior.update(detections, now, self.camera.size) if settings["behaviour_analysis"] else []
        if self.camera.running and frame is not None:
            zone_events = self.zone_monitor.update(detections, settings["zones"], self.camera.size, now, self.is_night)
            events = [*self._tamper_events, *zone_events, *events]
        if now < self._sos_until:
            events = [Event("sos", "SOS button pressed — help requested", "HIGH", confidence=1.0), *events]
        previous = self.result.level
        result = self.risk.evaluate(detections, events=events, is_night=self.is_night, motion=motion, settings=settings)
        with self._lock:
            self.detections, self.result, self.events = detections, result, events
            self._det_version += 1
        self._drive(result, detections)
        self._voice(result, previous, sos=self._sos_new, now=now)

        if result.level != previous:
            self.note("level", f"Risk {previous} → {result.level}: {result.reasons[0]}", result.level)
        if self._sos_new:  # every press is recorded and alerted, even if risk was already HIGH
            self._sos_new = False
            self._record_incident(result, detections, frame, sos=True)
        elif result.level != previous and LEVELS.index(result.level) > LEVELS.index(previous):
            self._record_incident(result, detections, frame)
        self._housekeeping(result, detections, now)
        return last_frame

    def _drive(self, result: RiskResult, detections: list[Detection]) -> None:
        people = sum(d.category == "person" for d in detections)
        self.hardware.configure(self.settings["ldr_dark_threshold"], self.settings["low_brightness"])
        strobe = result.level == "HIGH" and self.settings["strobe_on_high"]
        self.hardware.drive(result.brightness, result.buzzer, people=people, is_night_clock=self._clock_night(), strobe=strobe)

    def _housekeeping(self, result: RiskResult, detections: list[Detection], now: float) -> None:
        settings = self.settings
        self._account_energy(now)
        if settings["escalate_after_min"] and now - self._last_escalation_check >= 10:
            self._last_escalation_check = now
            for incident in self.store.pending_high_before(now - settings["escalate_after_min"] * 60):
                self.note("alert", f"No operator response to incident #{incident['id']} within "
                                   f"{settings['escalate_after_min']} min: sending automatically", "HIGH", incident["id"])
                self.dispatch_alert(incident["id"], confirmed=False, escalated=True)
        if self.camera.running and now - self._last_metric >= METRIC_INTERVAL:
            people = sum(d.category == "person" for d in detections)
            vehicles = sum(d.category == "vehicle" for d in detections)
            self.store.add_metric(people, vehicles, result.level, self.hardware.brightness)
            self._last_metric = now
        if now - self._last_purge >= PURGE_INTERVAL:
            removed = self.store.purge_older_than(settings["evidence_retention_days"])
            if removed:
                self.note("system", f"Removed {removed} incidents older than {settings['evidence_retention_days']} days")
            self._last_purge = now

    # ------------------------------------------------------------- heatmap
    def _add_heat(self, detections: list[Detection], frame, now: float) -> None:
        """Count where people's feet are, on a coarse grid; keep a face-blurred background picture."""
        h, w = frame.shape[:2]
        day = datetime.fromtimestamp(now, self.tz).strftime("%Y-%m-%d")
        if self._heat_day and day != self._heat_day:
            self._flush_heat()
        self._heat_day = day
        for d in detections:
            if d.category == "person":
                gx = min(HEAT_W - 1, max(0, int((d.box[0] + d.box[2]) / 2 / w * HEAT_W)))
                gy = min(HEAT_H - 1, max(0, int(d.box[3] / h * HEAT_H)))
                self._heat[gy * HEAT_W + gx] += 1
        if now - self._heat_flushed >= 60:
            self._flush_heat()
        if now - self._heat_bg_at >= HEAT_BACKGROUND_EVERY:
            self._heat_bg_at = now
            cv2.imwrite(str(EVIDENCE_DIR / HEAT_BACKGROUND), blur_faces(frame, detections), [cv2.IMWRITE_JPEG_QUALITY, 75])

    def _flush_heat(self) -> None:
        if self._heat_day and any(self._heat):
            self.store.add_heat(self._heat_day, self._heat)
        self._heat = [0] * (HEAT_W * HEAT_H)
        self._heat_flushed = time.time()

    def heatmap(self, days: int) -> dict:
        start = (datetime.now(self.tz) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        total = [0] * (HEAT_W * HEAT_H)
        for cells in [*self.store.heat_since(start), self._heat]:
            if len(cells) == len(total):
                total = [a + b for a, b in zip(total, cells, strict=True)]
        background = EVIDENCE_DIR / HEAT_BACKGROUND
        return {"width": HEAT_W, "height": HEAT_H, "cells": total, "peak": max(total),
                "background": f"/evidence/{HEAT_BACKGROUND}?t={int(background.stat().st_mtime)}" if background.exists() else None}

    # -------------------------------------------------------------- energy
    def _account_energy(self, now: float) -> None:
        """Integrate lamp power over time, next to a normal lamp at full power for every night hour."""
        e = self._energy
        dt = min(now - e["t"], 2.0) if e["t"] else 0.0  # a gap (sleep, pause) is not counted as lamp time
        e["t"] = now
        day = datetime.fromtimestamp(now, self.tz).strftime("%Y-%m-%d")
        if e["day"] and day != e["day"]:
            self._flush_energy()
        e["day"] = day
        watts = self.settings["lamp_watts"]
        e["lamp_wh"] += self.hardware.brightness / 100 * watts * dt / 3600
        if self.is_night:
            e["baseline_wh"] += watts * dt / 3600
            e["night_s"] += dt
        if now - e["flushed"] >= 60:
            self._flush_energy()

    def _flush_energy(self) -> None:
        e = self._energy
        if e["day"] and (e["lamp_wh"] or e["baseline_wh"]):
            self.store.add_energy(e["day"], e["lamp_wh"], e["baseline_wh"], e["night_s"])
        e["lamp_wh"] = e["baseline_wh"] = e["night_s"] = 0.0
        e["flushed"] = time.time()

    def energy_today(self) -> dict:
        cached_at, value = self._energy_today
        if time.time() - cached_at >= 10:
            value = self._energy_summary([datetime.now(self.tz).strftime("%Y-%m-%d")])
            self._energy_today = (time.time(), value)
        return value

    def _energy_summary(self, day_keys: list[str]) -> dict:
        rows = {r["day"]: dict(r) for r in self.store.energy_since(day_keys[0])}
        live = self._energy  # minute not yet written to the database
        if live["day"] in day_keys:
            row = rows.setdefault(live["day"], {"lamp_wh": 0.0, "baseline_wh": 0.0})
            row["lamp_wh"] += live["lamp_wh"]
            row["baseline_wh"] += live["baseline_wh"]
        lamp = [round(rows.get(d, {}).get("lamp_wh", 0) / 1000, 4) for d in day_keys]
        base = [round(rows.get(d, {}).get("baseline_wh", 0) / 1000, 4) for d in day_keys]
        saved = max(0.0, sum(base) - sum(lamp))
        s = self.settings
        return {
            "lamp_kwh": lamp, "baseline_kwh": base,
            "saved_kwh": round(saved, 3), "saved_cost": round(saved * s["tariff_per_kwh"], 2),
            "co2_kg": round(saved * s["co2_kg_per_kwh"], 2),
            "saving_pct": round(100 * saved / sum(base), 1) if sum(base) else None,
            "currency": s["currency"], "lamp_watts": s["lamp_watts"],
        }

    def _clock_night(self) -> bool:
        now = datetime.now(self.tz).strftime("%H:%M")
        start, end = self.settings["night_start"], self.settings["night_end"]
        return (start <= now or now < end) if start > end else (start <= now < end)

    def _night(self) -> tuple[bool, str]:
        source = self.settings["day_night_source"]
        hw = self.hardware
        has_ldr = hw.mode == "serial" and hw.online and hw.ldr is not None
        if has_ldr and source in ("ldr", "auto"):
            return hw.ldr < self.settings["ldr_dark_threshold"], "ldr"
        return self._clock_night(), "clock"

    # ----------------------------------------------------------- incidents
    def _record_incident(self, result: RiskResult, detections: list[Detection], frame, sos: bool = False) -> None:
        now = time.time()
        if not sos and now - self._last_incident.get(result.level, 0) < self.settings["incident_cooldown_s"]:
            return
        self._last_incident[result.level] = now
        snapshot = None
        if frame is not None:
            snapshot = f"{datetime.now(self.tz):%Y%m%d_%H%M%S}_{result.level.lower()}.jpg"
            cv2.imwrite(str(EVIDENCE_DIR / snapshot), self._overlay(frame, detections, self.events, evidence=True),
                        [cv2.IMWRITE_JPEG_QUALITY, 88])
        people = sum(d.category == "person" for d in detections)
        if sos:
            label, confidence = "sos", 1.0
        elif result.weapon:
            label, confidence = result.weapon.label, result.weapon.confidence
        elif result.event:
            label, confidence = result.event.label.split(" — ")[0].lower(), result.event.confidence
        else:
            reason = result.reasons[0].lower()
            label = "crowd" if "crowd" in reason else "loitering" if "linger" in reason else "night activity"
            persons = [d.confidence for d in detections if d.category == "person"]
            confidence = max(persons) if persons else None
        contacts = [c for c in self.store.contacts() if c["enabled"]]
        if result.level != "HIGH":
            alert_status = "none"
        elif not contacts:
            alert_status = "no_contacts"
        else:
            alert_status = "pending"
        location = self.settings["light_location"]
        incident = self.store.add_incident(
            ts=now, level=result.level, label=label, confidence=confidence, people=people,
            vehicles=sum(d.category == "vehicle" for d in detections), reasons=result.reasons,
            snapshot=snapshot, lat=location.get("lat"), lng=location.get("lng"), alert_status=alert_status,
        )
        self.note("incident", f"Incident #{incident['id']}: {result.level} – {label}", result.level, incident["id"])
        if self.settings["record_clips"] and self.camera.running:
            self.clips.capture(incident["id"], f"{datetime.now(self.tz):%Y%m%d_%H%M%S}_{result.level.lower()}_{incident['id']}")
        if alert_status == "pending" and sos:
            # a person asked for help: no AI judgement to confirm, so send at once in every mode
            self.dispatch_alert(incident["id"], confirmed=False)
        elif alert_status == "pending" and self.settings["alert_mode"] == "auto":
            if now - self._last_auto_alert >= self.settings["alert_cooldown_s"]:
                self._last_auto_alert = now
                self.dispatch_alert(incident["id"], confirmed=False)
            else:
                self.store.update_incident(incident["id"], alert_status="suppressed")
                wait = int(self.settings["alert_cooldown_s"] - (now - self._last_auto_alert))
                self.note("alert", f"Auto-alert for incident #{incident['id']} held back by the cooldown "
                                   f"({wait} s left); send it from Incident review if needed", "HIGH", incident["id"])

    def dispatch_alert(self, incident_id: int, confirmed: bool = True, escalated: bool = False) -> dict:
        incident = self.store.incident(incident_id)
        if incident is None:
            raise KeyError(incident_id)
        contacts = [c for c in self.store.contacts() if c["enabled"]]
        if not contacts:
            return self.store.update_incident(incident_id, alert_status="no_contacts")
        self.store.update_incident(incident_id, alert_status="sending")
        subject, body = self._alert_text(incident, confirmed, escalated)
        image = EVIDENCE_DIR / incident["snapshot"] if incident["snapshot"] else None

        def run() -> None:
            results = []
            for contact in contacts:
                ok, error = self.notifier.send(contact, subject, body, image)
                self.store.log_alert(incident_id, contact["id"], contact["channel"], ok, error)
                results.append(ok)
            status = "sent" if all(results) else "partial" if any(results) else "failed"
            self.store.update_incident(incident_id, alert_status=status)
            self.note("alert", f"Alert for incident #{incident_id}: {status} ({sum(results)}/{len(results)} contacts)",
                      incident["level"], incident_id)

        self.notifier.submit(run)
        return self.store.incident(incident_id)

    def _alert_text(self, incident: dict, confirmed: bool, escalated: bool = False) -> tuple[str, str]:
        when = datetime.fromtimestamp(incident["ts"], self.tz).strftime("%d %b %Y, %I:%M:%S %p %Z")
        location = self.settings["light_location"]
        lines = [f"Time: {when}"]
        if incident["lat"] is not None:
            name = location.get("label") or "Street light"
            lines.append(f"Location: {name} – https://maps.google.com/?q={incident['lat']},{incident['lng']}")
        lines.append(f"Detected: {incident['label']}"
                     + (f" ({incident['confidence']:.0%} confidence)" if incident["confidence"] else ""))
        lines.append(f"People in view: {incident['people']}")
        lines.extend(f"• {reason}" for reason in incident["reasons"])
        lines.append("")
        if incident["label"] == "sos":
            lines.append("Someone pressed the SOS button on this street light and is asking for help.")
        elif escalated:
            lines.append(f"No operator responded within {self.settings['escalate_after_min']} min, so this was sent "
                         "automatically. AI detection, not yet verified by a person.")
        else:
            lines.append("Confirmed by the Sentinel Street operator." if confirmed else
                         "Automatic AI detection – not yet verified by a person.")
        subject = ("🆘 Sentinel Street: SOS — help requested" if incident["label"] == "sos"
                   else f"⚠ Sentinel Street: {incident['level']} risk – {incident['label']}")
        return subject, "\n".join(lines)

    # -------------------------------------------------------------- stream
    def jpeg(self) -> bytes | None:
        frame_id, frame = self.camera.latest()
        if frame is None:
            return None
        with self._lock:
            key = (frame_id, self._det_version)
            cached = self._jpeg
            detections, events = list(self.detections), list(self.events)
        if cached and cached[0] == key:
            return cached[1]
        ok, buffer = cv2.imencode(".jpg", self._overlay(frame, detections, events), [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return None
        data = buffer.tobytes()
        with self._lock:
            self._jpeg = (key, data)
        return data

    # --------------------------------------------------------------- state
    def incidents_today(self) -> int:
        cached_at, value = self._today_cache
        if time.time() - cached_at < 2:
            return value
        midnight = datetime.now(self.tz).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        value = self.store.count_incidents(start=midnight)
        self._today_cache = (time.time(), value)
        return value

    def state(self) -> dict:
        with self._lock:
            detections = list(self.detections)
            result = self.result
            activity = list(self.activity)[:15]
        detector = self.detector
        cam = self.camera
        return {
            "time": time.time(),
            "camera": {"running": cam.running, "index": cam.index, "fps": round(cam.fps, 1), "mirror": cam.mirror,
                       "size": cam.size, "health": self.tamper.status if cam.running else "off"},
            "detector": {
                "loading": self.detector_loading, "ready": bool(detector and detector.ready),
                "error": detector.error if detector else "", "models": detector.models if detector else [],
                "device": detector.device if detector else "", "inference_ms": round(self.inference_ms),
                "model": detector.model_name if detector else self.settings["model"],
                "tracking": bool(detector and detector.tracking),
            },
            "risk": result.as_dict(),
            "counts": {k: sum(d.category == k for d in detections) for k in ("person", "vehicle", "weapon")},
            "detections": [d.as_dict() for d in detections[:30]],
            "events": [e.as_dict() for e in self.events],
            "night": {"is_night": self.is_night, "source": self.night_source},
            "hardware": self.hardware.readings(),
            "incidents_today": self.incidents_today(),
            "activity": activity,
            "alert_mode": self.settings["alert_mode"],
            "sos": {"active": time.time() < self._sos_until, "until": self._sos_until},
            "energy_today": self.energy_today(),
            "zones_active": sorted(self.zone_monitor.active),
        }

    # ------------------------------------------------------------ settings
    def update_settings(self, values: dict) -> dict:
        clean = {k: _coerce(k, v) for k, v in values.items()
                 if k in DEFAULT_SETTINGS and k not in ("light_location", "zones")}  # those have their own endpoints
        self.settings = self.store.save_settings(clean)
        if "mirror" in clean:
            self.camera.mirror = clean["mirror"]
        if "camera_index" in clean and not self.camera.running:
            self.camera.index = clean["camera_index"]
        model_changed = "model" in clean and (self.detector is None or clean["model"] != self.detector.model_name)
        pose_changed = "behaviour_analysis" in clean and self.detector is not None and clean["behaviour_analysis"] != self.detector.behaviour
        if model_changed or pose_changed:
            self.note("system", f"Loading {self.settings['model']}…")
            self.change_model(self.settings["model"])
        return self.settings

    def set_zones(self, raw_zones: list[dict]) -> list[dict]:
        import uuid

        if len(raw_zones) > 30:
            raise SettingsError("At most 30 zones")
        zones = []
        for raw in raw_zones:
            zone = validate_zone(raw)
            zone["id"] = zone["id"] or uuid.uuid4().hex[:8]
            zones.append(zone)
        self.settings = self.store.save_settings({"zones": zones})
        self.zone_monitor.reset()
        self.note("system", f"Zones updated ({len(zones)})")
        return zones

    def _overlay(self, frame, detections, events, evidence: bool = False):
        """Faces blurred (per the privacy setting), zones underneath, then boxes, skeletons and labels."""
        mode = self.settings["blur_faces"]
        if mode == "everywhere" or (mode == "live" and not evidence):
            frame = blur_faces(frame, detections)
        if self.settings["zones"]:
            frame = draw_zones(frame, self.settings["zones"], self.zone_monitor.active, self.is_night)
        return annotate(frame, detections, events)

    def set_location(self, lat: float, lng: float, accuracy: float | None, label: str, source: str) -> dict:
        if not all(math.isfinite(v) for v in (lat, lng) + ((accuracy,) if accuracy is not None else ())):
            raise SettingsError("Coordinates must be real numbers")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise SettingsError("Latitude must be -90..90 and longitude -180..180")
        location = {"lat": round(lat, 7), "lng": round(lng, 7),
                    "accuracy": round(accuracy, 1) if accuracy is not None else None,
                    "label": label.strip()[:80], "source": source[:20], "updated": time.time()}
        self.settings = self.store.save_settings({"light_location": location})
        self.note("system", f"Light location set ({source})")
        return location

    def connect_hardware(self, port: str) -> tuple[bool, str]:
        ok, message = self.hardware.connect(port)
        if ok:
            self.settings = self.store.save_settings({"serial_port": port})
        self.note("system", message)
        return ok, message

    # ----------------------------------------------------------- analytics
    def analytics(self, days: int) -> dict:
        tz = self.tz
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        start = today - timedelta(days=days - 1)
        incidents = self.store.incidents(start=start.timestamp(), limit=None)
        day_keys = [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        per_day = {key: Counter() for key in day_keys}
        by_hour = [0] * 24
        for item in incidents:
            local = datetime.fromtimestamp(item["ts"], tz)
            per_day.setdefault(local.strftime("%Y-%m-%d"), Counter())[item["level"]] += 1
            by_hour[local.hour] += 1
        reviewed = sum(i["status"] in ("reviewed", "false_alarm") for i in incidents)
        false_alarms = sum(i["status"] == "false_alarm" for i in incidents)
        peak = max(range(24), key=lambda h: by_hour[h]) if incidents else None

        since = time.time() - 86400
        buckets: dict[int, list[dict]] = {}
        for metric in self.store.metrics_since(since):
            buckets.setdefault(int(metric["ts"] // 1800) * 1800, []).append(metric)
        timeline = [{
            "ts": key,
            "people": round(sum(m["people"] for m in rows) / len(rows), 2),
            "vehicles": round(sum(m["vehicles"] for m in rows) / len(rows), 2),
        } for key, rows in sorted(buckets.items())]

        return {
            "days": day_keys,
            "per_day": {level: [per_day[d].get(level, 0) for d in day_keys] for level in ("HIGH", "MEDIUM")},
            "by_hour": by_hour,
            "by_label": Counter(i["label"] for i in incidents).most_common(8),
            "by_status": Counter(i["status"] for i in incidents),
            "kpis": {
                "total": len(incidents),
                "high": sum(i["level"] == "HIGH" for i in incidents),
                "medium": sum(i["level"] == "MEDIUM" for i in incidents),
                "false_alarm_rate": round(false_alarms / reviewed, 3) if reviewed else None,
                "peak_hour": peak,
                "alerts_sent": self.store.count_alerts_sent(start.timestamp()),
            },
            "timeline": timeline,
            "energy": self._energy_summary(day_keys),
        }
