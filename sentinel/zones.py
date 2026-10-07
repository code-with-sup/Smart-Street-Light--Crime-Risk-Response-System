"""Zones and tripwires drawn on the camera view.

Zone types (coordinates are fractions of the frame, 0..1, so they survive a resolution change):
  area  polygon with a rule:  "no_entry"  anyone inside raises the zone's level
                              "loiter"    one person inside longer than `seconds`
  line  tripwire: a person's path crossing it, in "any" direction, or only "a_to_b" (with the
        arrow the dashboard draws on the line) / "b_to_a" (against it). The arrow is the normal
        (dy, -dx) of the drawn line A->B: it points from the side where _side() > 0 to the other.

A person's position is their feet (bottom-centre of the box), so walking *in front of* a zone
drawn on the ground doesn't count. Each zone can be active "always" or only at "night".
"""

from __future__ import annotations

from dataclasses import dataclass

from .behavior import Event
from .detection import Detection

CROSSING_HOLD = 5.0   # a crossing is momentary; keep its event this long so the risk engine sees it
TRACK_TIMEOUT = 3.0
LEVELS = ("MEDIUM", "HIGH")
RULES = ("no_entry", "loiter")
DIRECTIONS = ("any", "a_to_b", "b_to_a")
SCHEDULES = ("always", "night")


class ZoneError(ValueError):
    pass


def validate_zone(raw: dict) -> dict:
    """Clean one zone from the API; raises ZoneError with a readable message."""
    try:
        kind = raw["type"]
        points = [[float(x), float(y)] for x, y in raw["points"]]
    except (KeyError, TypeError, ValueError):
        raise ZoneError("A zone needs a type and a list of [x, y] points") from None
    if kind not in ("area", "line"):
        raise ZoneError("Zone type must be area or line")
    if any(not (0 <= v <= 1) for p in points for v in p):
        raise ZoneError("Points must be fractions of the frame (0 to 1)")
    if kind == "area" and len(points) < 3:
        raise ZoneError("An area needs at least 3 points")
    if kind == "line" and len(points) != 2:
        raise ZoneError("A tripwire needs exactly 2 points")
    name = str(raw.get("name") or ("Area" if kind == "area" else "Tripwire")).strip()[:40]
    level = raw.get("level", "MEDIUM")
    schedule = raw.get("schedule", "always")
    if level not in LEVELS:
        raise ZoneError("Level must be MEDIUM or HIGH")
    if schedule not in SCHEDULES:
        raise ZoneError("Schedule must be always or night")
    zone = {"id": str(raw.get("id") or "")[:40], "name": name, "type": kind, "points": points,
            "level": level, "schedule": schedule, "enabled": bool(raw.get("enabled", True))}
    if kind == "area":
        rule = raw.get("rule", "no_entry")
        if rule not in RULES:
            raise ZoneError("Area rule must be no_entry or loiter")
        seconds = int(raw.get("seconds", 30))
        if not 3 <= seconds <= 3600:
            raise ZoneError("Loiter time must be 3 to 3600 seconds")
        zone.update(rule=rule, seconds=seconds)
    else:
        direction = raw.get("direction", "any")
        if direction not in DIRECTIONS:
            raise ZoneError("Direction must be any, a_to_b or b_to_a")
        zone["direction"] = direction
    return zone


def _inside(point, polygon) -> bool:
    """Ray casting point-in-polygon."""
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _side(a, b, p) -> float:
    """Sign tells which side of A->B the point is on (the dashboard's arrow points from + to -)."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _crosses(a, b, p, q) -> bool:
    """Do segments A-B (the tripwire) and P-Q (one step of a person's path) intersect?"""
    d1, d2 = _side(a, b, p), _side(a, b, q)
    d3, d4 = _side(p, q, a), _side(p, q, b)
    return d1 * d2 < 0 and d3 * d4 < 0


@dataclass
class _Track:
    last: tuple[float, float]
    seen: float
    entered: dict  # zone id -> time this person entered that area


class ZoneMonitor:
    def __init__(self) -> None:
        self._tracks: dict[int, _Track] = {}
        self._crossings: dict[str, tuple[float, Event]] = {}  # zone id -> (until, event)
        self.active: set[str] = set()  # zone ids triggered right now (for drawing)

    def reset(self) -> None:
        self._tracks.clear()
        self._crossings.clear()
        self.active = set()

    def update(self, detections: list[Detection], zones: list[dict], frame_size, now: float, is_night: bool) -> list[Event]:
        width, height = frame_size if frame_size and frame_size[0] else (0, 0)
        live = [z for z in zones if z.get("enabled", True) and (z.get("schedule") != "night" or is_night)]
        events: list[Event] = []
        self.active = set()
        if not width or not live:
            return events

        people = [d for d in detections if d.category == "person" and d.track_id is not None]
        for d in people:
            feet = ((d.box[0] + d.box[2]) / 2 / width, d.box[3] / height)
            track = self._tracks.get(d.track_id)
            previous = track.last if track else None
            if track is None:
                track = self._tracks[d.track_id] = _Track(feet, now, {})

            for zone in live:
                zid = zone["id"]
                if zone["type"] == "area":
                    if _inside(feet, zone["points"]):
                        track.entered.setdefault(zid, now)
                        stayed = now - track.entered[zid]
                        if zone["rule"] == "no_entry":
                            events.append(Event("zone_entry", f"Person #{d.track_id} entered {zone['name']}",
                                                zone["level"], (d.track_id,), d.box, 0.9))
                            self.active.add(zid)
                        elif stayed >= zone["seconds"]:
                            events.append(Event("zone_loiter", f"Person #{d.track_id} lingering in {zone['name']} for {int(stayed)} s",
                                                zone["level"], (d.track_id,), d.box, 0.8))
                            self.active.add(zid)
                    else:
                        track.entered.pop(zid, None)
                elif previous is not None:
                    a, b = zone["points"]
                    if _crosses(a, b, previous, feet):
                        a_to_b = _side(a, b, previous) > 0  # moved with the arrow (from the + side)
                        wanted = zone.get("direction", "any")
                        if wanted == "any" or (wanted == "a_to_b") == a_to_b:
                            event = Event("line_cross", f"Person #{d.track_id} crossed {zone['name']}",
                                          zone["level"], (d.track_id,), d.box, 0.9)
                            self._crossings[zid] = (now + CROSSING_HOLD, event)
            track.last, track.seen = feet, now

        for track_id in [k for k, t in self._tracks.items() if now - t.seen > TRACK_TIMEOUT]:
            del self._tracks[track_id]
        live_ids = {z["id"] for z in live}
        for zid, (until, event) in list(self._crossings.items()):
            if now > until or zid not in live_ids:
                del self._crossings[zid]
            else:
                events.append(event)
                self.active.add(zid)
        return events


def draw_zones(frame, zones: list[dict], active: set[str], is_night: bool):
    """Draw zones on a copy of the frame: amber, red while triggered; tripwires get their arrow."""
    import cv2
    import numpy as np

    out = frame.copy()
    h, w = out.shape[:2]
    overlay = out.copy()
    for zone in zones:
        if not zone.get("enabled", True):
            continue
        dormant = zone.get("schedule") == "night" and not is_night
        color = (60, 60, 230) if zone["id"] in active else (120, 120, 120) if dormant else (36, 165, 245)
        pts = np.array([[int(x * w), int(y * h)] for x, y in zone["points"]], np.int32)
        if zone["type"] == "area":
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(out, [pts], True, color, 2, cv2.LINE_AA)
            anchor = tuple(pts.min(axis=0))
        else:
            (ax, ay), (bx, by) = pts
            cv2.line(out, (ax, ay), (bx, by), color, 3, cv2.LINE_AA)
            if zone.get("direction", "any") != "any":
                dx, dy = bx - ax, by - ay
                length = max(1.0, (dx * dx + dy * dy) ** 0.5)
                nx, ny = dy / length, -dx / length  # same arrow as the detector and the dashboard
                if zone["direction"] == "b_to_a":
                    nx, ny = -nx, -ny
                mx, my = (ax + bx) // 2, (ay + by) // 2
                cv2.arrowedLine(out, (mx, my), (int(mx + nx * 40), int(my + ny * 40)), color, 3, cv2.LINE_AA, tipLength=0.4)
            anchor = (min(ax, bx), min(ay, by))
        label = zone["name"] + ("  (night)" if dormant else "")
        cv2.putText(out, label, (anchor[0] + 6, max(18, anchor[1] - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2, cv2.LINE_AA)
    return cv2.addWeighted(overlay, 0.18, out, 0.82, 0)
