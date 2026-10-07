"""PDF and CSV incident reports."""

from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo

from fpdf import FPDF

from .config import EVIDENCE_DIR

LEVEL_RGB = {"HIGH": (214, 40, 57), "MEDIUM": (230, 145, 20), "LOW": (20, 160, 110)}


def _ascii(text: str) -> str:
    """Core PDF fonts are Latin-1 only."""
    return (text.replace("—", "-").replace("–", "-").replace("•", "-").replace("…", "...")
            .encode("latin-1", "replace").decode("latin-1"))


def build_csv(incidents: list[dict], tz: ZoneInfo) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["id", "time", "level", "label", "confidence", "people", "vehicles",
                     "status", "alert_status", "lat", "lng", "reasons", "notes", "snapshot"])
    for item in incidents:
        writer.writerow([
            item["id"], datetime.fromtimestamp(item["ts"], tz).isoformat(timespec="seconds"), item["level"],
            item["label"], f"{item['confidence']:.2f}" if item["confidence"] is not None else "",
            item["people"], item["vehicles"], item["status"], item["alert_status"],
            item["lat"] or "", item["lng"] or "", "; ".join(item["reasons"]), item["notes"], item["snapshot"] or "",
        ])
    return out.getvalue()


def build_pdf(incidents: list[dict], *, start: datetime, end: datetime, tz: ZoneInfo, location: dict) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_fill_color(18, 20, 48)
    pdf.rect(0, 0, 210, 38, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_xy(14, 10)
    pdf.cell(0, 9, "Sentinel Street - Safety Report")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_xy(14, 22)
    period = f"{start:%d %b %Y} to {end:%d %b %Y}  |  Generated {datetime.now(tz):%d %b %Y %H:%M %Z}"
    pdf.cell(0, 6, _ascii(period))

    pdf.set_text_color(20, 24, 40)
    pdf.set_xy(14, 46)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    levels = Counter(i["level"] for i in incidents)
    labels = Counter(i["label"] for i in incidents)
    false_alarms = sum(i["status"] == "false_alarm" for i in incidents)
    if location.get("lat") is not None:
        where = f"{location.get('label') or 'Street light'} ({location['lat']:.5f}, {location['lng']:.5f})"
    else:
        where = "Location not set"
    lines = [
        f"Location: {where}",
        f"Incidents: {len(incidents)}   High: {levels.get('HIGH', 0)}   Medium: {levels.get('MEDIUM', 0)}   "
        f"False alarms: {false_alarms}",
        "Most common: " + (", ".join(f"{k} ({v})" for k, v in labels.most_common(4)) or "none"),
    ]
    for line in lines:
        pdf.set_x(14)
        pdf.cell(0, 6, _ascii(line), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.set_x(14)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, "Incident log", new_x="LMARGIN", new_y="NEXT")
    widths = (12, 38, 22, 38, 20, 22, 30)
    headers = ("#", "Time", "Level", "Detection", "Conf.", "People", "Status")
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(235, 238, 248)
    pdf.set_x(14)
    for width, header in zip(widths, headers, strict=True):
        pdf.cell(width, 7, header, border=0, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for item in incidents:
        pdf.set_x(14)
        values = (
            str(item["id"]), datetime.fromtimestamp(item["ts"], tz).strftime("%d %b %H:%M:%S"), item["level"],
            item["label"].title(), f"{item['confidence']:.0%}" if item["confidence"] is not None else "-",
            str(item["people"]), item["status"].replace("_", " "),
        )
        for index, (width, value) in enumerate(zip(widths, values, strict=True)):
            if index == 2:
                pdf.set_text_color(*LEVEL_RGB.get(item["level"], (20, 24, 40)))
            pdf.cell(width, 6, _ascii(value))
            pdf.set_text_color(20, 24, 40)
        pdf.ln()
    if not incidents:
        pdf.set_x(14)
        pdf.cell(0, 6, "No incidents recorded in this period.")

    evidence = [i for i in incidents if i["snapshot"] and (EVIDENCE_DIR / i["snapshot"]).exists()][:12]
    if evidence:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Evidence snapshots", new_x="LMARGIN", new_y="NEXT")
        x0, y, w, h = 14, pdf.get_y() + 2, 88, 58
        for index, item in enumerate(evidence):
            col = index % 2
            if col == 0 and index:
                y += h + 14
            if y + h + 12 > 285:
                pdf.add_page()
                y = 20
            x = x0 + col * (w + 6)
            pdf.image(str(EVIDENCE_DIR / item["snapshot"]), x=x, y=y, w=w, h=h, keep_aspect_ratio=True)
            pdf.set_xy(x, y + h + 1)
            pdf.set_font("Helvetica", "", 8)
            caption = f"#{item['id']} {item['level']} - {item['label']} - {datetime.fromtimestamp(item['ts'], tz):%d %b %H:%M:%S}"
            pdf.cell(w, 5, _ascii(caption))
    return bytes(pdf.output())
