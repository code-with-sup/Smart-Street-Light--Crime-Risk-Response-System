"""Paths, environment secrets and default settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = Path(os.environ.get("SENTINEL_DATA_DIR") or ROOT / "data")  # tests point this at a temp folder
EVIDENCE_DIR = DATA_DIR / "evidence"
DB_PATH = DATA_DIR / "sentinel.db"
WEB_DIR = ROOT / "web"
CUSTOM_WEAPON_WEIGHTS = ROOT / "runs" / "weapon_detector"  # legacy location from the original app
CUSTOM_MODELS_DIR = ROOT / "models" / "custom"            # drop trained .pt files here


def env(name: str, default: str = "") -> str:
    """Secrets come only from the environment / .env file, never from code."""
    return os.environ.get(name, default).strip()


# Operator-editable settings, persisted in SQLite. Secrets never live here.
DEFAULT_SETTINGS: dict = {
    "time_zone": "Asia/Kolkata",
    "model": "yolo11n",  # see detection.MODELS
    "camera_index": 0,
    "mirror": False,
    "confidence": 0.40,
    "weapon_confidence": 0.55,  # tuned on the weapon model's test split (see models/custom/README.txt)
    "behaviour_analysis": True,
    "tamper_detection": True,   # camera covered / blurred / turned away  # pose-based crime cues: fight, person down, hands up, running
    "detect_interval_ms": 250,
    "night_start": "18:30",
    "night_end": "06:00",
    "day_night_source": "auto",  # auto | clock | ldr
    "ldr_dark_threshold": 1500,  # raw ESP32 ADC 0-4095; below = dark
    "crowd_threshold": 6,
    "loiter_seconds": 60,
    "low_brightness": 20,
    "strobe_on_high": True,   # lamp flashes while risk is HIGH (deters, draws attention)
    "sos_hold_s": 60,
    "record_clips": True,
    "escalate_after_min": 5,  # HIGH alert not confirmed by an operator within this -> sent automatically (0 = never)
    "lamp_watts": 60,         # power of the street lamp at 100 %
    "tariff_per_kwh": 8.0,    # electricity price
    "currency": "₹",
    "co2_kg_per_kwh": 0.71,   # grid emission factor (India ~0.71)     # save a ~10 s video (5 s before + 5 s after) with each incident         # an SOS press keeps risk HIGH this long unless an operator clears it
    "alert_mode": "manual",  # manual = operator confirms, auto = send on HIGH
    "alert_cooldown_s": 120,
    "incident_cooldown_s": 45,
    "evidence_retention_days": 30,
    "zones": [],              # areas and tripwires drawn in Live monitoring (see zones.py)
    "serial_port": "",  # "" = simulator
    "light_location": {"lat": None, "lng": None, "accuracy": None, "label": "", "source": "", "updated": None},
}
