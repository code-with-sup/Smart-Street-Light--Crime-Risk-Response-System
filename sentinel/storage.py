"""SQLite persistence for incidents, contacts, alert log, metrics and settings."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from .config import DATA_DIR, DB_PATH, DEFAULT_SETTINGS, EVIDENCE_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    level TEXT NOT NULL,
    label TEXT NOT NULL,
    confidence REAL,
    people INTEGER NOT NULL DEFAULT 0,
    vehicles INTEGER NOT NULL DEFAULT 0,
    reasons TEXT NOT NULL DEFAULT '[]',
    snapshot TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    alert_status TEXT NOT NULL DEFAULT 'none',
    notes TEXT NOT NULL DEFAULT '',
    lat REAL,
    lng REAL
);
CREATE INDEX IF NOT EXISTS idx_incidents_ts ON incidents(ts);
CREATE TABLE IF NOT EXISTS contacts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    channel TEXT NOT NULL,
    address TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    incident_id INTEGER,
    contact_id INTEGER,
    channel TEXT,
    ok INTEGER NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS metrics(
    ts REAL NOT NULL,
    people INTEGER NOT NULL,
    vehicles INTEGER NOT NULL,
    level TEXT NOT NULL,
    brightness INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS heatmap(
    day TEXT PRIMARY KEY,            -- local date YYYY-MM-DD
    cells TEXT NOT NULL              -- JSON list of counts, row by row (HEAT_W x HEAT_H)
);
CREATE TABLE IF NOT EXISTS energy(
    day TEXT PRIMARY KEY,            -- local date YYYY-MM-DD
    lamp_wh REAL NOT NULL DEFAULT 0, -- what the smart lamp used
    baseline_wh REAL NOT NULL DEFAULT 0, -- a normal lamp at full power all night
    night_s REAL NOT NULL DEFAULT 0
);
"""

INCIDENT_STATUSES = ("new", "reviewed", "false_alarm")


def _incident(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["reasons"] = json.loads(item.get("reasons") or "[]")
    item["snapshot_url"] = f"/evidence/{item['snapshot']}" if item.get("snapshot") else None
    item["clip_url"] = f"/evidence/{item['clip']}" if item.get("clip") else None
    return item


class Store:
    def __init__(self, path: Path = DB_PATH) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(SCHEMA)
            # upgrade databases created before video clips existed
            columns = {row[1] for row in self._db.execute("PRAGMA table_info(incidents)")}
            if "clip" not in columns:
                self._db.execute("ALTER TABLE incidents ADD COLUMN clip TEXT")
            # an alert interrupted by a shutdown stays "sending" forever; let the operator resend it
            self._db.execute("UPDATE incidents SET alert_status = 'pending' WHERE alert_status = 'sending'")
            self._db.commit()

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    def _execute(self, sql: str, params: tuple = ()) -> int:
        with self._lock:
            cursor = self._db.execute(sql, params)
            self._db.commit()
            return cursor.lastrowid

    # ----------------------------------------------------------- settings
    def settings(self) -> dict:
        stored = {row["key"]: json.loads(row["value"]) for row in self._query("SELECT key, value FROM settings")}
        merged = json.loads(json.dumps(DEFAULT_SETTINGS))
        merged.update({k: v for k, v in stored.items() if k in DEFAULT_SETTINGS})
        return merged

    def save_settings(self, values: dict) -> dict:
        with self._lock:
            for key, value in values.items():
                if key in DEFAULT_SETTINGS:
                    self._db.execute(
                        "INSERT INTO settings(key, value) VALUES(?, ?) "
                        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                        (key, json.dumps(value)),
                    )
            self._db.commit()
        return self.settings()

    # ---------------------------------------------------------- incidents
    def add_incident(self, *, ts, level, label, confidence, people, vehicles, reasons, snapshot, lat, lng, alert_status) -> dict:
        incident_id = self._execute(
            "INSERT INTO incidents(ts, level, label, confidence, people, vehicles, reasons, snapshot, lat, lng, alert_status) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ts, level, label, confidence, people, vehicles, json.dumps(reasons), snapshot, lat, lng, alert_status),
        )
        return self.incident(incident_id)

    def incident(self, incident_id: int) -> dict | None:
        rows = self._query("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        return _incident(rows[0]) if rows else None

    def incidents(self, level: str = "", status: str = "", start: float | None = None,
                  end: float | None = None, limit: int | None = 200) -> list[dict]:
        sql, params = "SELECT * FROM incidents WHERE 1=1", []
        if level:
            sql += " AND level = ?"
            params.append(level)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if start is not None:
            sql += " AND ts >= ?"
            params.append(start)
        if end is not None:
            sql += " AND ts < ?"
            params.append(end)
        sql += " ORDER BY ts DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [_incident(row) for row in self._query(sql, tuple(params))]

    def count_incidents(self, start: float) -> int:
        return self._query("SELECT COUNT(*) FROM incidents WHERE ts >= ?", (start,))[0][0]

    def set_clip(self, incident_id: int, name: str) -> None:
        self._execute("UPDATE incidents SET clip = ? WHERE id = ?", (name, incident_id))

    def update_incident(self, incident_id: int, **fields) -> dict | None:
        allowed = {k: v for k, v in fields.items() if k in ("status", "notes", "alert_status") and v is not None}
        if allowed:
            assignments = ", ".join(f"{key} = ?" for key in allowed)
            self._execute(f"UPDATE incidents SET {assignments} WHERE id = ?", (*allowed.values(), incident_id))
        return self.incident(incident_id)

    def delete_incident(self, incident_id: int) -> bool:
        item = self.incident(incident_id)
        if not item:
            return False
        self._execute("DELETE FROM incidents WHERE id = ?", (incident_id,))
        self._remove_snapshot(item.get("snapshot"))
        self._remove_snapshot(item.get("clip"))
        return True

    def purge_older_than(self, days: int) -> int:
        cutoff = time.time() - days * 86400
        old = self._query("SELECT id, snapshot, clip FROM incidents WHERE ts < ?", (cutoff,))
        self._execute("DELETE FROM incidents WHERE ts < ?", (cutoff,))
        self._execute("DELETE FROM metrics WHERE ts < ?", (cutoff,))
        self._execute("DELETE FROM alert_log WHERE ts < ?", (cutoff,))
        for row in old:
            self._remove_snapshot(row["snapshot"])
            self._remove_snapshot(row["clip"])
        return len(old)

    @staticmethod
    def _remove_snapshot(name: str | None) -> None:
        if name:
            (EVIDENCE_DIR / Path(name).name).unlink(missing_ok=True)

    # ----------------------------------------------------------- contacts
    def contacts(self) -> list[dict]:
        rows = self._query("SELECT * FROM contacts ORDER BY created")
        return [{**dict(row), "enabled": bool(row["enabled"])} for row in rows]

    def contact(self, contact_id: int) -> dict | None:
        rows = self._query("SELECT * FROM contacts WHERE id = ?", (contact_id,))
        return {**dict(rows[0]), "enabled": bool(rows[0]["enabled"])} if rows else None

    def add_contact(self, name: str, channel: str, address: str) -> dict:
        contact_id = self._execute(
            "INSERT INTO contacts(name, channel, address, enabled, created) VALUES(?, ?, ?, 1, ?)",
            (name, channel, address, time.time()),
        )
        return self.contact(contact_id)

    def update_contact(self, contact_id: int, **fields) -> dict | None:
        allowed = {k: v for k, v in fields.items() if k in ("name", "channel", "address", "enabled") and v is not None}
        if "enabled" in allowed:
            allowed["enabled"] = int(bool(allowed["enabled"]))
        if allowed:
            assignments = ", ".join(f"{key} = ?" for key in allowed)
            self._execute(f"UPDATE contacts SET {assignments} WHERE id = ?", (*allowed.values(), contact_id))
        return self.contact(contact_id)

    def delete_contact(self, contact_id: int) -> None:
        self._execute("DELETE FROM contacts WHERE id = ?", (contact_id,))

    # ---------------------------------------------------------- alert log
    def log_alert(self, incident_id: int | None, contact_id: int, channel: str, ok: bool, error: str = "") -> None:
        self._execute(
            "INSERT INTO alert_log(ts, incident_id, contact_id, channel, ok, error) VALUES(?, ?, ?, ?, ?, ?)",
            (time.time(), incident_id, contact_id, channel, int(ok), error),
        )

    def count_alerts_sent(self, start: float) -> int:
        """Delivered incident alerts (test messages excluded)."""
        return self._query("SELECT COUNT(*) FROM alert_log WHERE ok = 1 AND incident_id IS NOT NULL AND ts >= ?",
                           (start,))[0][0]

    def alert_log(self, limit: int = 50) -> list[dict]:
        rows = self._query(
            "SELECT a.*, c.name AS contact_name FROM alert_log a LEFT JOIN contacts c ON c.id = a.contact_id "
            "ORDER BY a.ts DESC LIMIT ?", (limit,))
        return [{**dict(row), "ok": bool(row["ok"])} for row in rows]

    # ------------------------------------------------------------ metrics
    def add_metric(self, people: int, vehicles: int, level: str, brightness: int) -> None:
        self._execute(
            "INSERT INTO metrics(ts, people, vehicles, level, brightness) VALUES(?, ?, ?, ?, ?)",
            (time.time(), people, vehicles, level, brightness),
        )

    def add_energy(self, day: str, lamp_wh: float, baseline_wh: float, night_s: float) -> None:
        self._execute(
            "INSERT INTO energy(day, lamp_wh, baseline_wh, night_s) VALUES(?, ?, ?, ?) "
            "ON CONFLICT(day) DO UPDATE SET lamp_wh = lamp_wh + excluded.lamp_wh, "
            "baseline_wh = baseline_wh + excluded.baseline_wh, night_s = night_s + excluded.night_s",
            (day, lamp_wh, baseline_wh, night_s),
        )

    def add_heat(self, day: str, cells: list[int]) -> None:
        with self._lock:
            row = self._db.execute("SELECT cells FROM heatmap WHERE day = ?", (day,)).fetchone()
            if row:
                old = json.loads(row["cells"])
                if len(old) == len(cells):
                    cells = [a + b for a, b in zip(old, cells, strict=True)]
            self._db.execute("INSERT INTO heatmap(day, cells) VALUES(?, ?) ON CONFLICT(day) DO UPDATE SET cells = excluded.cells",
                             (day, json.dumps(cells)))
            self._db.commit()

    def heat_since(self, day: str) -> list[list[int]]:
        return [json.loads(row["cells"]) for row in self._query("SELECT cells FROM heatmap WHERE day >= ?", (day,))]

    def energy_since(self, day: str) -> list[dict]:
        return [dict(row) for row in self._query("SELECT * FROM energy WHERE day >= ? ORDER BY day", (day,))]

    def pending_high_before(self, cutoff: float) -> list[dict]:
        """HIGH incidents whose alert is still waiting for an operator."""
        rows = self._query("SELECT * FROM incidents WHERE level = 'HIGH' AND alert_status = 'pending' AND ts < ?", (cutoff,))
        return [_incident(row) for row in rows]

    def metrics_since(self, start: float) -> list[dict]:
        return [dict(row) for row in self._query("SELECT * FROM metrics WHERE ts >= ? ORDER BY ts", (start,))]
