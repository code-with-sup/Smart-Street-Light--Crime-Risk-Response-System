"""Sentinel Street — responsive day/night dashboard with camera feed.

Run: python3 smart_street_light.py
For laptop or USB camera support: python3 -m pip install -r requirements.txt
"""

from __future__ import annotations

from datetime import datetime
import math
from pathlib import Path
import sys
import tkinter as tk
from tkinter import font as tkfont, messagebox
import webbrowser
from zoneinfo import ZoneInfo



try:
    import cv2
    if hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"):
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except ImportError:
    cv2 = None

try:
    from PIL import Image, ImageOps, ImageTk
except ImportError:
    Image = ImageOps = ImageTk = None


class SmartStreetLightApp(tk.Tk):
    """Responsive light/dark dashboard with interactive camera controls."""

    BASE_WIDTH = 1655
    TOP_STRIP = 49
    BASE_HEIGHT = 901
    PREVIEW = (332, 440, 819, 335)  # x, y, width, height after title-strip removal
    CLOCK_CARDS = {
        "dark": (1360, 111, 1638, 231),
        "light": (1333, 99, 1639, 225),
    }
    ASSETS = Path(__file__).with_name("assets")
    TIME_ZONES = (
        ("India • IST", "Asia/Kolkata"),
        ("Dubai • GST", "Asia/Dubai"),
        ("London • UK", "Europe/London"),
        ("New York • ET", "America/New_York"),
        ("Los Angeles • PT", "America/Los_Angeles"),
        ("Singapore • SGT", "Asia/Singapore"),
        ("Tokyo • JST", "Asia/Tokyo"),
        ("Sydney • AEST/AEDT", "Australia/Sydney"),
    )
    NAV_ITEMS = (
        ("Overview", "⌂", 144, 203), ("Live monitoring", "▣", 205, 267),
        ("Incident review", "▤", 269, 331), ("GPS tracking", "●", 333, 394),
        ("Alert contacts", "♟", 396, 457), ("Sensors & lights", "▦", 459, 520),
        ("Analytics", "▥", 522, 582), ("Reports", "▤", 584, 646),
        ("Settings", "⚙", 648, 710),
    )

    camera = None
    camera_running = False
    camera_index = 0
    mirror_camera = False
    camera_failures = 0
    max_camera_failures = 24
    pending_camera_frame = None
    detect_every_n_frames = 6
    knife_detect_every_n_frames = 12
    camera_frame_number = 0
    last_weapon_detections = ()
    last_knife_detections = ()
    people_count = 0
    vehicle_count = 0
    event_count = 0
    threat_active = False
    detector = None
    knife_detector = None

    def __init__(self) -> None:
        super().__init__()
        self.title("Sentinel Street | Smart Safety Dashboard")
        # Keep the dashboard frameless; provide an explicit close control instead.
        self.overrideredirect(True)
        self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        self.minsize(1000, 600)
        self.dark_mode = True
        # Sentinel Street starts on India Standard Time. The clock card lets
        # an operator temporarily inspect other locations when needed.
        self.time_zone_label = "India • IST"
        self.time_zone_name = "Asia/Kolkata"
        self.time_zone = ZoneInfo(self.time_zone_name)
        self.time_zone_popup = None
        self.time_zone_buttons = {}
        self.camera = None
        self.camera_running = False
        self.camera_index = 0
        self.mirror_camera = False
        self.camera_failures = 0
        self.max_camera_failures = 24
        self.pending_camera_frame = None
        self.detect_every_n_frames = 6
        # YOLO11n is a second, generic detector for knives.  Sampling it less
        # often keeps the dashboard responsive on a CPU-only laptop.
        self.knife_detect_every_n_frames = 12
        self.camera_frame_number = 0
        self.last_weapon_detections = []
        self.last_knife_detections = []
        self.people_count = 0
        self.vehicle_count = 0
        self.event_count = 0
        self.threat_active = False
        self.detector = self._load_weapon_detector()
        self.knife_detector = self._load_knife_detector()
        self.active_nav = "Overview"
        self.module_view = None
        self.fullscreen_camera = False
        self.latest_frame = None
        self.scale_x = self.scale_y = 1.0
        self.video_photo = None
        self.reference_photo = None
        self._ui_photos = []
        self._actions = []
        self._picker_actions = []
        self._layout = {}
        self._resize_job = None
        self._scrollbar_visible = False
        self._last_cursor = ""
        self.references = self._load_templates()
        self.scenes = {
            mode: reference.crop((332, 488, 1151, 735))
            for mode, reference in self.references.items()
        }

        self.canvas = tk.Canvas(self, bg="#020B1C", highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self._scroll_canvas)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.configure(yscrollcommand=self._set_scrollbar)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Motion>", self._on_hover)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda _event: self._scroll_by(-3))
        self.canvas.bind("<Button-5>", lambda _event: self._scroll_by(3))
        self.bind("<Escape>", lambda _event: self._handle_escape())
        self.bind("<Prior>", lambda _event: self._scroll_by(-12))
        self.bind("<Next>", lambda _event: self._scroll_by(12))
        self.bind("<Home>", lambda _event: self._scroll_canvas("moveto", 0))
        self.bind("<End>", lambda _event: self._scroll_canvas("moveto", 1))
        self.after_idle(self._render_template)
        self.after(1000, self._refresh_clock)
        self.bind("<Command-q>", lambda _event: self._close())
        self.bind("<Control-q>", lambda _event: self._close())
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ------------------------------------------------------------------ #
    #  Inline YOLO detector helpers (no external weapon_detector module)   #
    # ------------------------------------------------------------------ #

    class _Detection:
        """Minimal result object compatible with _draw_detection."""
        __slots__ = ("box", "label", "confidence")
        def __init__(self, box, label, confidence):
            self.box = box          # (x1, y1, x2, y2) ints
            self.label = label      # str
            self.confidence = confidence  # 0.0–1.0

    class _YOLOWeaponDetector:
        """Custom-trained weapon detectors from runs/weapon_detector."""
        def __init__(self, weights_paths, conf=0.25):
            from ultralytics import YOLO  # type: ignore[import-not-found]
            if isinstance(weights_paths, (str, Path)):
                weights_paths = [weights_paths]
            self._models = [YOLO(str(p)) for p in weights_paths]
            self._conf = conf
            self.all_classes = set()
            for m in self._models:
                self.all_classes.update(m.names.values())

        def detect(self, bgr_frame):
            detections = []
            for model in self._models:
                results = model.predict(bgr_frame, conf=self._conf, verbose=False)
                for r in results:
                    for box in r.boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        label = model.names[int(box.cls[0])]
                        conf = float(box.conf[0])
                        detections.append(SmartStreetLightApp._Detection((x1, y1, x2, y2), label, conf))
            return detections

    class _YOLOKnifeDetector:
        """COCO yolo11n detector for edged/blunt weapons (knife, scissors, baseball bat) plus scene analytics."""
        def __init__(self, weights_path, conf=0.25):
            from ultralytics import YOLO  # type: ignore[import-not-found]
            self._model = YOLO(str(weights_path))
            self._conf = conf
            self.weapon_class_ids = {}
            for k, v in self._model.names.items():
                v_lower = v.lower()
                if v_lower in ("knife", "scissors", "baseball bat"):
                    self.weapon_class_ids[k] = v_lower
            self.last_people_count = 0
            self.last_vehicle_count = 0

        def detect(self, bgr_frame):
            # Target weapon classes + person (0) + vehicles (bicycle=1, car=2, motorcycle=3, bus=5, truck=7)
            target_classes = [0, 1, 2, 3, 5, 7] + list(self.weapon_class_ids.keys())
            results = self._model.predict(
                bgr_frame, conf=self._conf, classes=target_classes, verbose=False
            )
            detections = []
            people = 0
            vehicles = 0
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    if cls_id in self.weapon_class_ids:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        label = self.weapon_class_ids[cls_id]
                        detections.append(SmartStreetLightApp._Detection((x1, y1, x2, y2), label, conf))
                    elif cls_id == 0:
                        people += 1
                    elif cls_id in (1, 2, 3, 5, 7):
                        vehicles += 1
            self.last_people_count = people
            self.last_vehicle_count = vehicles
            return detections

    def _load_weapon_detector(self):
        """Load custom-trained weapon detectors from runs/weapon_detector."""
        weights_root = Path(__file__).with_name("runs") / "weapon_detector"
        candidates = [
            weights_root / "weapon_dataset_v1" / "weights" / "best.pt",
            weights_root / "weapon_demo" / "weights" / "best.pt",
            weights_root / "street_weapon_v1" / "weights" / "best.pt",
        ]
        available_weights = [c for c in candidates if c.exists()]
        if not available_weights:
            print("Weapon detector: no trained weights found in runs/weapon_detector/")
            return None
        try:
            detector = SmartStreetLightApp._YOLOWeaponDetector(available_weights)
            classes = sorted(list(detector.all_classes))
            models_loaded = [w.parent.parent.name for w in available_weights]
            print(f"Weapon detector ready: {models_loaded} — classes: {classes}")
            return detector
        except Exception as error:
            print(f"Weapon detector could not load: {error}")
            return None

    def _load_knife_detector(self):
        """Load yolo11n.pt or yolo26n.pt for edged weapons (knives, scissors, bats)."""
        candidates = (
            Path(__file__).with_name("yolo11n.pt"),
            Path(__file__).with_name("yolo26n.pt"),
        )
        weights = next((c for c in candidates if c.exists()), None)
        if weights is None:
            print("Edged weapon detector: yolo11n.pt/yolo26n.pt not found beside the dashboard.")
            return None
        try:
            detector = SmartStreetLightApp._YOLOKnifeDetector(weights)
            print(f"Edged weapon detector ready: {weights.name} (classes: {list(detector.weapon_class_ids.values())})")
            return detector
        except Exception as error:
            print(f"Edged weapon detector could not load: {error}")
            return None

    def _load_templates(self) -> dict[str, object]:
        """Load the exact dark/light dashboard artwork supplied for this project."""
        if Image is None:
            messagebox.showerror("Pillow is needed", "Install the display package with:\n\npython3 -m pip install -r requirements.txt")
            self.destroy()
            return {}
        sources = {
            "dark": self.ASSETS / "dashboard-dark-reference.png",
            "light": self.ASSETS / "dashboard-light-reference.png",
        }
        missing = [str(path) for path in sources.values() if not path.exists()]
        if missing:
            messagebox.showerror("Dashboard artwork missing", "Required dashboard templates were not found:\n\n" + "\n".join(missing))
            self.destroy()
            return {}
        return {
            mode: Image.open(path).convert("RGB").crop((0, self.TOP_STRIP, self.BASE_WIDTH, self.TOP_STRIP + self.BASE_HEIGHT))
            for mode, path in sources.items()
        }

    def _on_resize(self, _event=None) -> None:
        self._close_time_zone_picker()
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(70, self._render_template)

    @staticmethod
    def _compute_layout(width: int, height: int) -> dict:
        """Fit cards, not a screenshot: use one font scale and flexible photo heights."""
        scale = min(max(1, width) / 1655, max(1, height) / 780)
        w, h = width / scale, height / scale
        left, right, gap = 314, w - 20, 16
        hero_h = min(242, max(200, h * .255))
        stats_y, stats_h = hero_h + 4, 114
        body_y, bottom = stats_y + stats_h + gap, h - 24
        camera_right = left + (right - left - gap) * .66
        side_left = camera_right + gap
        location_bottom = body_y + min(228, (bottom - body_y) * .44)
        nav_step = min(65, max(44, (h - 340) / 9))
        return {
            "scale": scale, "width": w, "height": h,
            "hero": (293, 0, w, hero_h),
            "clock": (right - 278, hero_h - 128, right, hero_h - 8),
            "stats": tuple((left + i * (right-left+gap)/3, stats_y,
                            left + i * (right-left+gap)/3 + (right-left-2*gap)/3,
                            stats_y + stats_h) for i in range(3)),
            "camera": (left, body_y, camera_right, bottom),
            "preview": (left + 18, body_y + 66, camera_right - 18, bottom - 88),
            "location": (side_left, body_y, right, location_bottom),
            "risk": (side_left, location_bottom + 14, right, bottom),
            "module": (left, 24, right, bottom),
            "nav": tuple((20, 144+i*nav_step, 275, 144+(i+1)*nav_step-7) for i in range(9)),
            "system": (20, h - 158, 275, h - 91),
            "day": (20, h - 77, 142, h - 25),
            "night": (152, h - 77, 275, h - 25),
        }

    def _render_template(self) -> None:
        self._resize_job = None
        if not self.winfo_exists() or not self.references:
            return
        if self.fullscreen_camera:
            self._render_fullscreen_camera()
            return
        width, height = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
        self._layout = self._compute_layout(width, height)
        self.scale_x = self.scale_y = self._layout["scale"]
        self._actions = []
        self._ui_photos = []
        self.canvas.delete("all")
        self.canvas.configure(scrollregion=(0, 0, width, height))
        self.canvas.configure(bg=self._palette()["background"])
        self._draw_sidebar()
        if self.module_view:
            self._draw_module_view()
        else:
            self._draw_overview()
        if self.time_zone_popup is not None:
            self._draw_time_zone_picker()

    def _point(self, x: float, y: float) -> tuple[int, int]:
        return round(x * self.scale_x), round(y * self.scale_y)

    def _palette(self) -> dict:
        if self.dark_mode:
            return {"background": "#020B1C", "sidebar": "#030E21", "card": "#07172E",
                    "edge": "#203D61", "text": "#F7F9FF", "muted": "#B0C6E8",
                    "soft": "#11233E", "purple": "#9E61FF", "green": "#00E49A",
                    "blue": "#3594FF"}
        return {"background": "#F0F5FF", "sidebar": "#FCFDFF", "card": "#FFFFFF",
                "edge": "#D8E3F5", "text": "#07112A", "muted": "#526B98",
                "soft": "#F1F5FD", "purple": "#692CFF", "green": "#00B67C",
                "blue": "#086CFA"}

    def _text(self, x, y, text="", size=16, color=None, bold=False, anchor="w", tags=(), **kwargs):
        return self.canvas.create_text(*self._point(x, y), text=text, anchor=anchor,
            fill=color or self._palette()["text"],
            font=("Avenir Next", -max(8, round(size * self.scale_y)), "bold" if bold else "normal"),
            tags=tags, **kwargs)

    def _card(self, bounds, fill=None, edge=None, radius=12, tags=()):
        x1, y1 = self._point(*bounds[:2])
        x2, y2 = self._point(*bounds[2:])
        self._draw_rounded_rectangle(x1, y1, x2, y2, max(3, round(radius*self.scale_x)),
            fill=fill or self._palette()["card"], outline=edge or self._palette()["edge"],
            width=max(1, round(self.scale_x)), tags=tags)

    def _register_action(self, name, bounds, callback, picker=False):
        actions = self._picker_actions if picker else self._actions
        actions.append((name, bounds, callback))

    def _button(self, bounds, text, callback, name, primary=False, enabled=True, icon=None, tags=(), picker=False):
        p = self._palette()
        fill, edge = ("#6728F9", "#B889FF") if primary and enabled else (p["soft"], p["edge"])
        self._card(bounds, fill=fill, edge=edge, radius=9, tags=tags)
        left, top, right, bottom = bounds
        color = "#FFFFFF" if primary and enabled else p["text"] if enabled else p["muted"]
        center_y = (top+bottom)/2
        if icon:
            self._icon(icon, left+22, center_y, 19, color, tags=tags)
        self._text((left+right)/2 + (8 if icon else 0), center_y, text, 16, color, True, "center", tags)
        if enabled:
            self._register_action(name, bounds, callback, picker=picker)

    def _icon(self, name, x, y, size=25, color=None, tags=()):
        """Small consistent vector icons: no platform-dependent emoji substitutes."""
        c = color or self._palette()["muted"]
        s = size/24
        def point(px, py): return self._point(x+(px-12)*s, y+(py-12)*s)
        def line(coords, **kw):
            flat = [v for px, py in zip(coords[::2], coords[1::2]) for v in point(px, py)]
            return self.canvas.create_line(*flat, fill=c, width=max(1, round(2*s*self.scale_x)), tags=tags, **kw)
        def rect(a,b,d,e,fill=""):
            self.canvas.create_rectangle(*point(a,b), *point(d,e), fill=fill, outline=c,
                width=max(1, round(2*s*self.scale_x)), tags=tags)
        def oval(a,b,d,e,fill=""):
            self.canvas.create_oval(*point(a,b), *point(d,e), fill=fill, outline=c,
                width=max(1, round(2*s*self.scale_x)), tags=tags)
        def polygon(coords, fill=""):
            flat = [v for px,py in zip(coords[::2], coords[1::2]) for v in point(px,py)]
            self.canvas.create_polygon(*flat, fill=fill, outline=c, width=max(1, round(2*s*self.scale_x)), tags=tags)
        if name == "camera":
            rect(2,5,16,19,c); polygon((17,9,23,5,23,19,17,15), c)
        elif name == "monitor":
            rect(1,3,19,17); polygon((20,8,24,5,24,15,20,12), c); line((10,17,10,22,16,22)); line((5,22,16,22))
        elif name == "home":
            polygon((1,11,12,1,23,11,19,11,19,22,14,22,14,15,10,15,10,22,5,22,5,11), c)
        elif name == "shield":
            polygon((12,1,21,5,20,14,17,19,12,23,7,19,4,14,3,5)); line((12,2,12,21))
        elif name == "people":
            oval(3,2,11,10,c); oval(15,4,21,10,c); polygon((1,22,2,16,5,13,9,13,13,16,14,22),c)
            polygon((16,13,20,13,23,17,23,22,17,22),c)
        elif name == "pin":
            oval(4,1,20,17,c); polygon((5,11,12,24,19,11),c); oval(9,5,15,11,self._palette()["card"])
        elif name in ("document", "report"):
            polygon((4,1,15,1,21,7,21,23,4,23)); line((15,1,15,7,21,7)); line((8,12,17,12)); line((8,17,17,17))
        elif name == "chip":
            rect(5,5,19,19); rect(9,9,15,15)
            for t in (7,12,17):
                line((t,1,t,5)); line((t,19,t,23)); line((1,t,5,t)); line((19,t,23,t))
        elif name == "bars":
            rect(2,13,6,23,c); rect(10,2,14,23,c); rect(18,8,22,23,c)
        elif name == "gear":
            oval(4,4,20,20); oval(9,9,15,15)
            for coords in ((12,0,12,4),(12,20,12,24),(0,12,4,12),(20,12,24,12),(3,3,6,6),(18,18,21,21),(3,21,6,18),(18,6,21,3)):
                line(coords)
        elif name == "fullscreen":
            for coords in ((1,8,1,1,8,1),(16,1,23,1,23,8),(1,16,1,23,8,23),(16,23,23,23,23,16)): line(coords)
        elif name == "sun":
            oval(7,7,17,17,c)
            for coords in ((12,0,12,4),(12,20,12,24),(0,12,4,12),(20,12,24,12),(3,3,6,6),(18,18,21,21),(3,21,6,18),(18,6,21,3)): line(coords)
        elif name == "moon":
            self.canvas.create_arc(*point(3,1), *point(23,23), start=70, extent=260, style="arc", outline=c,
                width=max(2, round(3*s*self.scale_x)), tags=tags)
        elif name == "play": polygon((5,2,22,12,5,22),c)
        elif name == "stop": rect(4,4,20,20,c)
        elif name == "flip":
            rect(4,6,20,18); line((0,12,24,12), arrow="both")
        elif name == "refresh":
            self.canvas.create_arc(*point(3,3), *point(21,21), start=40, extent=290, style="arc", outline=c,
                width=max(1, round(2*s*self.scale_x)), tags=tags)
            polygon((16,2,22,3,21,9),c)
        elif name == "info":
            oval(1,1,23,23); line((12,11,12,18)); oval(11,6,13,8,c)
        elif name == "car":
            polygon((3,10,6,4,18,4,21,10,23,12,23,20,1,20,1,12)); line((4,10,20,10)); oval(4,14,7,17,c); oval(17,14,20,17,c)
        elif name == "close": line((5,5,19,19)); line((5,19,19,5))
        elif name == "spark": polygon((12,0,16,8,24,12,16,16,12,24,8,16,0,12,8,8),c)

    def _clock_now(self) -> datetime:
        return datetime.now(self.time_zone)

    def _clock_card_bounds(self):
        return self._layout.get("clock", self.CLOCK_CARDS["dark" if self.dark_mode else "light"])

    def _is_clock_zone_label(self, x: float, y: float) -> bool:
        """Only the visible location label is an interactive clock control."""
        if self.module_view or self.fullscreen_camera:
            return False
        bounds = self.canvas.bbox("clock-zone")
        if bounds is None:
            return False
        padding = 4 * self.scale_x
        px, py = x * self.scale_x, y * self.scale_y
        return bounds[0] - padding <= px <= bounds[2] + padding and bounds[1] - padding <= py <= bounds[3] + padding

    def _time_zone_rows(self):
        """Use one instant for all cities, including their daylight-saving offsets."""
        instant = self._clock_now()
        rows = []
        for label, zone_name in self.TIME_ZONES:
            local = instant.astimezone(ZoneInfo(zone_name))
            city = label.split(" • ", 1)[0]
            offset = local.strftime("%z")
            rows.append((label, zone_name, f"{city} • {local.tzname()}", local.strftime("%I:%M %p"),
                         f"{local.strftime('%a, %d %b')} • UTC{offset[:3]}:{offset[3:]}"))
        return rows

    def _draw_rounded_rectangle(self, x1: int, y1: int, x2: int, y2: int, radius: int, **style) -> None:
        """Draw a filled rounded card using only Tk's standard Canvas API."""
        canvas = self.canvas
        fill = style.get("fill", "")
        edge = style.get("outline") or fill
        border = max(0, int(style.get("width", 0)))
        tags = style.get("tags")

        base_tags = (tags,) if isinstance(tags,str) else tuple(tags or ())
        def draw_layer(left: int, top: int, right: int, bottom: int, corner: int, color: str, layer: str) -> None:
            layer_tags = base_tags + tuple(tag+"-"+layer for tag in base_tags if tag.endswith("-card"))
            draw_style = {"fill": color, "outline": "", "tags": layer_tags}
            canvas.create_rectangle(left + corner, top, right - corner, bottom, **draw_style)
            canvas.create_rectangle(left, top + corner, right, bottom - corner, **draw_style)
            canvas.create_oval(left, top, left + corner * 2, top + corner * 2, **draw_style)
            canvas.create_oval(right - corner * 2, top, right, top + corner * 2, **draw_style)
            canvas.create_oval(left, bottom - corner * 2, left + corner * 2, bottom, **draw_style)
            canvas.create_oval(right - corner * 2, bottom - corner * 2, right, bottom, **draw_style)

        draw_layer(x1, y1, x2, y2, radius, edge, "border")
        if border:
            draw_layer(
                x1 + border,
                y1 + border,
                x2 - border,
                y2 - border,
                max(0, radius - border),
                fill,
                "fill",
            )

    def _draw_clock(self) -> None:
        """Update existing text items so moving the cursor cannot cause flicker."""
        if self.fullscreen_camera or self.module_view or not self.canvas.winfo_exists():
            return
        canvas = self.canvas
        left, top, right, bottom = self._clock_card_bounds()
        colors = (
            {"card": "#020D2B", "edge": "#153A68", "time": "#FFFFFF", "date": "#B9C9EA", "zone": "#8CA5D3", "icon": "#5E82FF"}
            if self.dark_mode
            else {"card": "#FFFFFF", "edge": "#E6EDF8", "time": "#060C2A", "date": "#526B9E", "zone": "#6A83B2", "icon": "#1976F8"}
        )
        now = self._clock_now()
        # Match the greeting periods in the selected timezone, not the UI theme.
        icon = "☀️" if 4 <= now.hour < 17 else "🌙"
        time_text = now.strftime("%I:%M %p")
        date_text = now.strftime("%A, %d %B %Y")
        city = self.time_zone_label.split(" • ", 1)[0]
        zone_text = f"{city} • {now.tzname() or self.time_zone_name}"
        if not canvas.find_withtag("clock"):
            x1, y1 = self._point(left, top)
            x2, y2 = self._point(right, bottom)
            self._draw_rounded_rectangle(
                x1, y1, x2, y2, max(10, round(20 * self.scale_x)),
                fill=colors["card"], outline=colors["edge"],
                width=max(1, round(self.scale_x)), tags="clock",
            )
            positions = (
                ("clock-time", right - 58, top + 43, "e", "time", 38, "bold"),
                ("clock-date", (left + right) / 2, bottom - 40, "center", "date", 16, "normal"),
                ("clock-zone", (left + right) / 2, bottom - 17, "center", "zone", 13, "bold"),
            )
            for tag, x, y, anchor, color, size, weight in positions:
                canvas.create_text(*self._point(x, y), anchor=anchor, fill=colors[color],
                                   font=("Avenir Next", -max(8, round(size * self.scale_y)), weight),
                                   tags=("clock", tag))
            emoji_font = ("Apple Color Emoji" if sys.platform == "darwin" else
                          "Segoe UI Emoji" if sys.platform == "win32" else "Noto Color Emoji")
            canvas.create_text(*self._point(right-27, top+43), anchor="center", fill=colors["icon"],
                               font=(emoji_font, -max(10, round(28*self.scale_y))),
                               tags=("clock", "clock-icon"))
        # Reserve space for the emoji on the right and keep the date in its card.
        for tag, text, size, available, weight in (
            ("clock-time", time_text, 38, (right - left - 76) * self.scale_x, "bold"),
            ("clock-date", date_text, 16, (right - left - 20) * self.scale_x, "normal"),
        ):
            font_size = max(8, round(size * self.scale_y))
            measured_font = tkfont.Font(self, family="Avenir Next", size=-font_size, weight=weight)
            while font_size > 8 and measured_font.measure(text) > available:
                font_size -= 1
                measured_font.configure(size=-font_size)
            canvas.itemconfigure(tag, text=text, font=("Avenir Next", -font_size, weight))
        canvas.itemconfigure("clock-icon", text=icon)
        canvas.itemconfigure("clock-zone", text=zone_text)
        canvas.itemconfigure("greeting", text=self._greeting(now.hour) + ",")

    @staticmethod
    def _greeting(hour: int) -> str:
        if 4 <= hour < 12:
            return "Good morning"
        if 12 <= hour < 17:
            return "Good afternoon"
        return "Good evening"

    def _refresh_clock(self) -> None:
        """Keep the clock accurate without repainting the entire dashboard."""
        if self.winfo_exists():
            self._draw_clock()
            self._update_time_zone_displays()
            self.after(1000, self._refresh_clock)

    def _show_time_zone_picker(self) -> None:
        """Open the chooser only after a click on the location label."""
        if self.time_zone_popup is not None:
            self._close_time_zone_picker()
            return
        self.time_zone_popup = True
        self._draw_time_zone_picker()

    def _draw_time_zone_picker(self) -> None:
        self.canvas.delete("zone-picker")
        self._picker_actions = []
        p, tags = self._palette(), "zone-picker"
        right = self._layout["width"] - 22
        left = right - 390
        top = min(self._clock_card_bounds()[3] + 10, self._layout["height"] - 598)
        top = max(20, top)
        bottom = top + 576
        self._card((left+4, top+6, right+4, bottom+6), fill=p["soft"], tags=tags)
        self._card((left, top, right, bottom), edge=p["purple"], tags=tags)
        self._text(left+20, top+30, "Clock time zone", 23, bold=True, tags=tags)
        self._icon("close", right-26, top+28, 20, tags=tags)
        self._register_action("close-zone", (right-46, top+9, right-8, top+48), self._close_time_zone_picker, picker=True)
        self._text(left+20, top+64, "Choose a location · India is the default", 13, p["muted"], tags=tags)
        for index, (label, zone_name) in enumerate(self.TIME_ZONES):
            y = top + 88 + index*59
            self._card((left+12, y, right-12, y+53), fill=p["soft"], tags=(tags, f"picker-zone-{index}-card"))
            self._text(left+26, y+18, size=15, bold=True, tags=(tags, f"picker-zone-{index}-title"))
            self._text(right-26, y+18, size=17, bold=True, anchor="e", tags=(tags, f"picker-zone-{index}-time"))
            self._text(left+26, y+39, size=11, color=p["muted"], tags=(tags, f"picker-zone-{index}-detail"))
            self._register_action(zone_name, (left+12, y, right-12, y+53),
                lambda title=label, zone=zone_name: self._set_time_zone(title, zone), picker=True)
        self._update_time_zone_displays()

    def _close_time_zone_picker(self) -> None:
        self.time_zone_popup = None
        self.time_zone_buttons = {}
        self._picker_actions = []
        if hasattr(self, "canvas") and self.canvas.winfo_exists():
            self.canvas.delete("zone-picker")

    def _set_time_zone(self, label: str, zone_name: str) -> None:
        self.time_zone_label = label
        self.time_zone_name = zone_name
        self.time_zone = ZoneInfo(zone_name)
        self._close_time_zone_picker()
        self._draw_clock()
        self._update_time_zone_displays()
        self._show_toast(f"Clock set to {label}")

    def _update_time_zone_displays(self) -> None:
        """Update the chooser and Settings with live times without rebuilding either."""
        for index, (_label, zone_name, title, time_text, detail) in enumerate(self._time_zone_rows()):
            for prefix, visible in (("picker", self.time_zone_popup is not None), ("world", self.module_view == "Settings")):
                if not visible:
                    continue
                selected = zone_name == self.time_zone_name
                if self.dark_mode:
                    card, edge = ("#291B4D", "#A87BFF") if selected else ("#102442", "#294465")
                else:
                    card, edge = ("#F0E9FF", "#713BFF") if selected else ("#F5F8FD", "#D4DFEE")
                self.canvas.itemconfigure(f"{prefix}-zone-{index}-card-fill", fill=card)
                self.canvas.itemconfigure(f"{prefix}-zone-{index}-card-border", fill=edge)
                self.canvas.itemconfigure(f"{prefix}-zone-{index}-title", text=title)
                self.canvas.itemconfigure(f"{prefix}-zone-{index}-time", text=time_text)
                self.canvas.itemconfigure(f"{prefix}-zone-{index}-detail", text=detail)

    def _draw_sidebar(self) -> None:
        p, h = self._palette(), self._layout["height"]
        self.canvas.create_rectangle(0, 0, *self._point(293, h), fill=p["sidebar"], outline=p["edge"])
        self._card((28, 27, 95, 94), fill="#7032FF", edge="#A777FF")
        self._text(61.5, 61, "S", 43, "#FFFFFF", True, "center")
        self._text(110, 45, "Sentinel", 28, bold=True)
        self._text(110, 76, "Street", 28, bold=True)
        self._text(110, 104, "Smart Street Safety System", 11.5, p["muted"])
        self._icon("close", 266, 18, 14)
        self._register_action("quit", (252, 3, 281, 32), self._close)
        self.canvas.create_line(*self._point(20, 127), *self._point(275, 127), fill=p["edge"])
        icons = ("home", "monitor", "document", "pin", "people", "chip", "bars", "report", "gear")
        for (label, _symbol, _start, _end), icon, bounds in zip(self.NAV_ITEMS, icons, self._layout["nav"]):
            active = self.active_nav == label
            if active:
                self._card(bounds, fill="#6424FF", edge="#B280FF", radius=9)
            color = "#FFFFFF" if active else p["muted"]
            center_y = (bounds[1]+bounds[3])/2
            self._icon(icon, 53, center_y, 27, color)
            self._text(100, center_y, label, 20, color, active)
            self._register_action("nav-"+label, bounds, lambda name=label: self._navigate(name))
        left, top, right, bottom = self._layout["system"]
        self._card((left, top, right, bottom))
        self._dot(left+29, (top+bottom)/2, p["green"], 10)
        self._text(left+62, top+24, "System ready", 18, bold=True)
        self._text(left+62, top+46, "Local camera processing", 12, p["muted"])
        self._button(self._layout["day"], "Day", lambda: self._set_theme(False), "day", not self.dark_mode, icon="sun")
        self._button(self._layout["night"], "Night", lambda: self._set_theme(True), "night", self.dark_mode, icon="moon")

    def _dot(self, x, y, color, radius=6, tags=()):
        self.canvas.create_oval(*self._point(x-radius,y-radius), *self._point(x+radius,y+radius),
                                fill=color, outline="", tags=tags)

    def _photo(self, source, bounds, tags=(), fade=False):
        x1, y1 = self._point(*bounds[:2])
        x2, y2 = self._point(*bounds[2:])
        photo = ImageOps.fit(source, (max(1,x2-x1), max(1,y2-y1)), method=Image.Resampling.LANCZOS)
        if fade:
            photo = photo.convert("RGBA")
            color = self._palette()["background"]
            overlay = Image.new("RGBA", photo.size, color)
            alpha = Image.new("L", (photo.width, 1))
            alpha.putdata([round(255 * max(0, 1 - x/(photo.width*.64))) for x in range(photo.width)])
            overlay.putalpha(alpha.resize(photo.size))
            photo = Image.alpha_composite(photo, overlay)
        image = ImageTk.PhotoImage(photo)
        self._ui_photos.append(image)
        self.canvas.create_image(x1, y1, image=image, anchor="nw", tags=tags)

    def _draw_overview(self) -> None:
        p = self._palette()
        mode = "dark" if self.dark_mode else "light"
        # Only use the city photography from the reference. All labels and
        # controls are real UI, so no frozen greeting/time/LIVE label can leak.
        hero_photo = self.references[mode].crop((775, 16, 1655, 96))
        self._photo(hero_photo, self._layout["hero"], fade=True)
        self._text(337, 39, "S E N T I N E L   S T R E E T", 12, p["muted"], True)
        self._text(337, 83, self._greeting(self._clock_now().hour)+",", 46, bold=True, tags="greeting")
        self._text(337, 137, "Safety Operator", 46, p["purple"], True)
        self._icon("spark", 742, 137, 35, p["purple"])
        self._text(337, 182, "Observe  •  Analyse  •  Respond before risk escalates", 18)
        self._draw_clock()
        self._draw_stats_cards()
        left, top, right, bottom = self._layout["camera"]
        self._card(self._layout["camera"])
        self._card((left+18, top+15, left+55, top+51), fill="#1671FF", edge="#1671FF", radius=8)
        self._icon("camera", left+36, top+33, 23, "#FFFFFF")
        self._text(left+73, top+33, "Live Camera Feed", 26, bold=True)
        self._dot(right-190, top+33, p["green"] if self.camera_running else p["muted"])
        self._text(right-173, top+33, "CAMERA LIVE" if self.camera_running else "CAMERA READY", 13, p["muted"], True)
        self._icon("fullscreen", right-33, top+33, 22)
        self._register_action("camera-fullscreen", (right-52, top+12, right-14, top+54), self.toggle_camera_fullscreen)
        self._draw_live_frame()
        control_y = bottom-71
        start_right = left+18+(right-left-36)*.29
        stop_right = start_right+12+(right-left-36)*.17
        switch_right = stop_right+12+(right-left-36)*.20
        self._button((left+18, control_y, start_right, bottom-18), "START CAMERA", self.start_camera,
                     "camera-start", True, not self.camera_running, "play")
        self._button((start_right+12, control_y, stop_right, bottom-18), "STOP", self.stop_camera,
                     "camera-stop", enabled=self.camera_running, icon="stop")
        self._button((stop_right+12, control_y, switch_right, bottom-18), "SWITCH", self.switch_camera,
                     "camera-switch", icon="refresh")
        self._button((switch_right+12, control_y, switch_right+65, bottom-18), "", self.flip_camera,
                     "camera-flip", enabled=self.camera_running, icon="flip")
        self._text(right-19, bottom-5, "Local processing only · Camera off" if not self.camera_running else "Local processing only", 11,
                   p["muted"], anchor="e")
        self._draw_risk_card()

    def _draw_stats_cards(self) -> None:
        p = self._palette()
        self.canvas.delete("stats-cards")
        has_threat = bool(self.last_weapon_detections or self.last_knife_detections)
        if has_threat:
            first_detection = (self.last_weapon_detections or self.last_knife_detections)[0]
            threat_name = first_detection.label.replace("_", " ").title()
            safety_val = "ALERT!"
            safety_sub = f"{threat_name} detected in feed"
            safety_color = "#E60028"
            contacts_val = "DISPATCH READY"
            contacts_sub = "Threat flagged for review"
            contacts_color = "#E60028"
        elif self.camera_running:
            safety_val = "Secure"
            safety_sub = "AI surveillance active"
            safety_color = "#00C68D"
            contacts_val = "Standby"
            contacts_sub = "Automated pipeline ready"
            contacts_color = "#7937FF"
        else:
            safety_val = "Standby" if self.detector or self.knife_detector else "Not analysing"
            safety_sub = "Weapon detection enabled" if self.detector or self.knife_detector else "No analysis model configured"
            safety_color = "#00C68D" if self.detector or self.knife_detector else p["muted"]
            contacts_val = "Standby"
            contacts_sub = "Alerts not active"
            contacts_color = "#7937FF"

        cam_val = f"Live (Cam {self.camera_index + 1})" if self.camera_running else "Standby"
        cam_sub = "Camera connected" if self.camera_running else "Ready to begin monitoring"

        statuses = (
            ("CAMERA STATUS", cam_val, cam_sub, "camera", "#1671FF"),
            ("SAFETY LEVEL", safety_val, safety_sub, "shield", safety_color),
            ("EMERGENCY CONTACTS", contacts_val, contacts_sub, "people", contacts_color),
        )
        for index, (bounds, (title, value, subtitle, icon, color)) in enumerate(zip(self._layout["stats"], statuses)):
            left, top, right, bottom = bounds
            self._card(bounds, tags="stats-cards")
            self._card((left+20, top+20, left+94, bottom-20), fill=color, edge=color, tags="stats-cards")
            self._icon(icon, left+57, (top+bottom)/2, 36, "#FFFFFF", tags="stats-cards")
            self._text(left+116, top+29, title, 14, p["muted"], True, tags="stats-cards")
            self._text(left+116, top+61, value, 26, bold=True, tags="stats-cards")
            self._text(left+116, bottom-22, subtitle, 14, p["muted"], tags="stats-cards")
            dot_color = "#E60028" if (index == 1 and has_threat) else (p["green"] if index == 0 and self.camera_running else p["muted"])
            self._dot(right-22, top+29, dot_color, 6, tags="stats-cards")

    def _draw_risk_card(self):
        p = self._palette()
        left, top, right, bottom = self._layout["risk"]
        self.canvas.delete("risk-card")
        self._card(self._layout["risk"], tags="risk-card")
        has_threat = bool(self.last_weapon_detections or self.last_knife_detections)
        icon_color = "#E60028" if has_threat else "#00C68D"
        self._card((left+17,top+14,left+54,top+51), fill=icon_color, edge=icon_color, radius=8, tags="risk-card")
        self._icon("bars", left+35, top+32, 24, "#FFFFFF", tags="risk-card")
        self._text(left+69, top+33, "Risk Analysis", 20, bold=True, tags="risk-card")
        compact = bottom - top < 280

        if has_threat:
            first_detection = (self.last_weapon_detections or self.last_knife_detections)[0]
            threat_name = first_detection.label.replace("_", " ").title()
            threat_desc = f"{threat_name} identified in live stream!"
            status_text = "THREAT DETECTED"
            status_color = "#E60028"
            score_num = 88 if self.last_weapon_detections else 74
            score_text = str(score_num)
            arc_color = "#E60028"
            arc_extent = -round(score_num / 100.0 * 360)
        elif self.camera_running:
            status_text = "Active Surveillance"
            status_color = p["green"]
            threat_desc = "Street monitored. Object detection models operational."
            score_num = min(12 + self.people_count * 3 + self.vehicle_count * 2, 35)
            score_text = str(score_num)
            arc_color = p["green"]
            arc_extent = -round(score_num / 100.0 * 360)
        else:
            status_text = "No active analysis"
            status_color = p["green"]
            threat_desc = "Weapon presence is not proof of a crime.\nVerified analysis is required before alerts."
            score_text = "—"
            arc_color = p["green"]
            arc_extent = -260

        self._text(left+18, top+74, status_text, 23, status_color, True, tags="risk-card")
        self._text(left+18, top+(108 if compact else 130), threat_desc,
                   12 if compact else 13, p["muted"], width=round((right-left-156)*self.scale_x), tags="risk-card")
        center_x, center_y, radius = right-76, top+(98 if compact else 113), 35 if compact else 59
        self.canvas.create_oval(*self._point(center_x-radius,center_y-radius), *self._point(center_x+radius,center_y+radius),
            outline=p["edge"], width=max(2,round(12*self.scale_x)), tags="risk-card")
        self.canvas.create_arc(*self._point(center_x-radius,center_y-radius), *self._point(center_x+radius,center_y+radius),
            start=90, extent=arc_extent, style="arc", outline=arc_color, width=max(2,round(12*self.scale_x)), tags="risk-card")
        self._text(center_x, center_y-17, "RISK\nSCORE", 11, p["muted"], anchor="center", tags="risk-card")
        self._text(center_x, center_y+23, score_text, 33, bold=True, anchor="center", tags="risk-card")
        metrics_y = bottom - 87
        width = (right - left - 30) / 3

        people_val = str(self.people_count) if self.camera_running else "—"
        veh_val = str(self.vehicle_count) if self.camera_running else "—"
        event_val = str(self.event_count)

        for i, (label, icon, value) in enumerate((("People", "people", people_val), ("Vehicles", "car", veh_val), ("Events", "document", event_val))):
            x = left + 10 + i * (width + 5)
            self._card((x, metrics_y, x+width, bottom-11), fill=p["soft"], radius=8, tags="risk-card")
            self._icon(icon, x+21, metrics_y+24, 19, tags="risk-card")
            self._text(x+40, metrics_y+23, label, 10, p["muted"], tags="risk-card")
            self._text(x+40, metrics_y+48, value, 23, bold=True, tags="risk-card")

    def _set_scrollbar(self, first: str, last: str) -> None:
        """Only show a scrollbar when the exact design is taller than its window."""
        self.scrollbar.set(first, last)
        needed = float(first) > 0.0 or float(last) < 0.9999
        if needed == self._scrollbar_visible:
            return
        self._scrollbar_visible = needed
        if needed:
            self.scrollbar.grid(row=0, column=1, sticky="ns")
        else:
            self.scrollbar.grid_remove()

    def _on_wheel(self, event) -> None:
        steps = -int(event.delta / 120) if event.delta else 0
        self._scroll_by(steps or (-1 if event.delta > 0 else 1))

    def _scroll_by(self, steps: int) -> None:
        self._scroll_canvas("scroll", steps, "units")

    def _scroll_canvas(self, *args) -> None:
        """Dismiss the chooser consistently for wheel, scrollbar and key scrolling."""
        self._close_time_zone_picker()
        self.canvas.yview(*args)

    def _base_position(self, event) -> tuple[float, float]:
        return (
            self.canvas.canvasx(event.x) / self.scale_x,
            self.canvas.canvasy(event.y) / self.scale_y,
        )

    def _hot_zone(self, x: float, y: float) -> bool:
        if self._is_clock_zone_label(x, y):
            return True
        actions = self._picker_actions if self.time_zone_popup is not None else self._actions
        return any(left <= x <= right and top <= y <= bottom for _name, (left,top,right,bottom), _callback in actions)

    def _on_hover(self, event) -> None:
        x, y = self._base_position(event)
        cursor = "hand2" if self._hot_zone(x, y) else ""
        if cursor != self._last_cursor:
            self.canvas.configure(cursor=cursor)
            self._last_cursor = cursor

    def _scaled_preview(self) -> tuple[int, int, int, int]:
        left, top, right, bottom = self._layout["preview"]
        x, y = self._point(left, top)
        x2, y2 = self._point(right, bottom)
        return x, y, max(1,x2-x), max(1,y2-y)

    def _draw_live_frame(self) -> None:
        if self.module_view or self.fullscreen_camera:
            return
        left, top, right, bottom = self._layout["preview"]
        x, y, width, height = self._scaled_preview()
        live = self.camera_running and self.latest_frame is not None
        source = self.latest_frame if live else self.scenes["dark" if self.dark_mode else "light"]
        frame = ImageOps.fit(source,(width,height),method=Image.Resampling.LANCZOS)
        self.video_photo = ImageTk.PhotoImage(frame)
        self.canvas.delete("live-camera")
        self.canvas.create_image(x, y, image=self.video_photo, anchor="nw", tags="live-camera")
        tags="live-camera"
        has_threat = bool(self.last_weapon_detections or self.last_knife_detections)
        if has_threat:
            first_detection = (self.last_weapon_detections or self.last_knife_detections)[0]
            threat_name = first_detection.label.replace('_', ' ').upper()
            self._card((left+12, top+12, left+230, top+44), fill="#E60028", edge="#FF4D6D", radius=6, tags=tags)
            self._text(left+24, top+28, f"⚠️ ALERT: {threat_name} DETECTED", 12, "#FFFFFF", True, tags=tags)
        else:
            self._card((left+12,top+12,left+(95 if live else 175),top+44), fill="#00C68D" if live else "#17233D", edge="#00C68D" if live else "#17233D", radius=6, tags=tags)
            self._text(left+24,top+28,"● LIVE" if live else "CAMERA OFF · PREVIEW",13,"#FFFFFF",True,tags=tags)
        if live:
            self._card((right-201,top+12,right-12,top+44),fill="#071020",edge="#071020",radius=6,tags=tags)
            self._text(right-22,top+28,self._clock_now().strftime("%Y-%m-%d %H:%M:%S"),12,"#FFFFFF",anchor="e",tags=tags)
        self._card((right-45,bottom-44,right-6,bottom-6),fill="#071020",edge="#071020",radius=6,tags=tags)
        self._icon("fullscreen",right-25,bottom-25,23,"#FFFFFF",tags)
        if not any(a[0] == "preview-fullscreen" for a in self._actions):
            self._register_action("preview-fullscreen",(right-45,bottom-44,right-6,bottom-6),self.toggle_camera_fullscreen)
        self.canvas.tag_raise("zone-picker")

    def _render_fullscreen_camera(self) -> None:
        """Render the preview or active webcam feed across the entire dashboard window."""
        if not self.winfo_exists() or not self.references:
            return
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self._actions = []
        self._register_action("exit-fullscreen", ((width-160)/self.scale_x, 11/self.scale_y,
                              (width-18)/self.scale_x,45/self.scale_y),self.toggle_camera_fullscreen)
        source = self.latest_frame
        if source is None:
            source = self.scenes["dark" if self.dark_mode else "light"]
        image = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS)
        self.video_photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.video_photo, anchor="nw", tags="fullscreen")
        has_threat = bool(self.last_weapon_detections or self.last_knife_detections)
        top_bar_fill = "#A8001D" if has_threat else "#061126"
        self.canvas.create_rectangle(0, 0, width, 56, fill=top_bar_fill, outline="", tags="fullscreen")
        if has_threat:
            first_detection = (self.last_weapon_detections or self.last_knife_detections)[0]
            threat_name = first_detection.label.replace('_', ' ').upper()
            label = f"⚠️  SECURITY ALERT: {threat_name} DETECTED IN CAMERA FEED  •  FULL SCREEN"
        else:
            label = "●  LIVE CAMERA  •  FULL SCREEN" if self.camera_running else "CAMERA OFF  •  PREVIEW IMAGE"
        self.canvas.create_text(24, 28, text=label, anchor="w", fill="#FFFFFF", font=("Avenir Next", -18, "bold"), tags="fullscreen")
        self.canvas.create_rectangle(width - 160, 11, width - 18, 45, fill="#713BFF", outline="#B59BFF", tags="fullscreen")
        self.canvas.create_text(width - 89, 28, text="EXIT · ESC", fill="#FFFFFF", font=("Avenir Next", -15, "bold"), tags="fullscreen")
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def _draw_module_view(self) -> None:
        """Display a practical function page while preserving the selected sidebar state."""
        if not self.module_view:
            return
        p = self._palette()
        left, top, right, bottom = self._layout["module"]
        self._card(self._layout["module"], edge=p["purple"])
        self._text(left+30, top+42, self.module_view, 34, bold=True)
        self._button((right-165,top+22,right-22,top+65), "Overview", lambda: self._navigate("Overview"), "back-overview")
        subtitle = {
            "Incident review": "Review detected incidents, captured evidence, and alert decisions.",
            "GPS tracking": "Live system location with permission, accuracy and update time. No IP-location estimates.",
            "Alert contacts": "Manage the phone numbers that receive verified emergency alerts.",
            "Sensors & lights": "Test connected sensors, street lights, and the emergency buzzer.",
            "Analytics": "View safety trends and verified incident patterns.",
            "Reports": "Generate a time-stamped safety report from recorded events.",
            "Settings": "Choose the clock location. The greeting and camera timestamps use the same time zone.",
        }.get(self.module_view, "This module is ready for configuration.")
        self._text(left+30,top+98,subtitle,17,p["muted"],width=round((right-left-60)*self.scale_x))
        self._module_content()

    def _module_content(self) -> None:
        if self.module_view == "Settings":
            self._draw_time_zone_settings()
            return
        p = self._palette()
        left, top, right, bottom = self._layout["module"]
        if self.module_view == "Incident review":
            headline, detail, action = "No incidents recorded", "New verified incidents and saved evidence will appear here.", "Open incident log"
        elif self.module_view == "Alert contacts":
            headline, detail, action = "Emergency contacts: 0 of 2", "Add up to two trusted phone numbers for a verified emergency alert.", "Add alert contact"
        elif self.module_view == "Sensors & lights":
            headline, detail, action = "Hardware module offline", "Arduino sensor, buzzer and light controls will appear when connected.", "Test hardware connection"
        elif self.module_view == "Analytics":
            headline, detail, action = "No safety data yet", "Analytics will become available after events have been analysed.", "View analytics guide"
        elif self.module_view == "Reports":
            headline, detail, action = "No report generated", "Reports will include incident time, location, risk and captured evidence.", "Generate sample report"
        else:
            headline, detail, action = "Dashboard preferences", "Camera, privacy and evidence-retention settings are managed here.", "Open settings"
        self._card((left+30,top+160,right-30,top+360),fill=p["soft"])
        self._text(left+55,top+211,headline,28,p["green"],True)
        self._text(left+55,top+263,detail,17,p["muted"],width=round((right-left-110)*self.scale_x))
        self._text(left+55,top+319,"This integration is not configured yet.",14,p["muted"])

    def _settings_time_zone_bounds(self, index: int):
        column, row = index % 2, index // 2
        x, y, right, bottom = self._layout["module"]
        width = (right-x-78)/2
        row_height = min(102, (bottom-y-305)/4)
        left, top = x+30+column*(width+18), y+202+row*row_height
        return left, top, left+width, top+row_height-10

    def _settings_time_zone_at(self, x: float, y: float):
        if self.module_view != "Settings":
            return None
        for index, zone in enumerate(self.TIME_ZONES):
            left, top, right, bottom = self._settings_time_zone_bounds(index)
            if left <= x <= right and top <= y <= bottom:
                return zone
        return None

    def _draw_time_zone_settings(self) -> None:
        p = self._palette()
        x,y,right,bottom = self._layout["module"]
        self._text(x+30,y+162,"World clocks · Select a city",23,bold=True)
        for index, (label,zone_name) in enumerate(self.TIME_ZONES):
            left, top, right, bottom = self._settings_time_zone_bounds(index)
            self._card((left,top,right,bottom),tags=("module",f"world-zone-{index}-card"))
            for tag, x, y, anchor, color, size, weight in (
                ("title", left + 18, top + 24, "w", p["text"], 20, "bold"),
                ("time", right - 18, top + 24, "e", p["text"], 25, "bold"),
                ("detail", left + 18, bottom - 23, "w", p["muted"], 13, "normal"),
            ):
                self._text(x,y,size=size,color=color,bold=weight=="bold",anchor=anchor,tags=("module",f"world-zone-{index}-{tag}"))
            self._register_action("setting-zone-"+zone_name,(left,top,right,bottom),lambda title=label,zone=zone_name:self._set_time_zone(title,zone))
        self._update_time_zone_displays()



    def _on_click(self, event) -> None:
        """Use the very same bounds that drew each control, at any screen size."""
        self.canvas.focus_set()
        if self.fullscreen_camera:
            if self.canvas.winfo_width()-160 <= event.x <= self.canvas.winfo_width()-18 and 11 <= event.y <= 45:
                self.toggle_camera_fullscreen()
            return
        x, y = self._base_position(event)

        if self._is_clock_zone_label(x, y):
            self._show_time_zone_picker()
            return
        actions = self._picker_actions if self.time_zone_popup is not None else self._actions
        for _name,(left,top,right,bottom),callback in reversed(actions):
            if left <= x <= right and top <= y <= bottom:
                callback()
                return
        if self.time_zone_popup is not None:
            self._close_time_zone_picker()

    def _navigate(self, name):
        self._close_time_zone_picker()
        self.active_nav = name
        self.module_view = None if name in ("Overview","Live monitoring") else name
        self.canvas.yview_moveto(0)
        self._render_template()



    def _set_theme(self, dark: bool) -> None:
        if self.dark_mode == dark:
            return
        self._close_time_zone_picker()
        self.dark_mode = dark
        self._render_template()

    def toggle_camera_fullscreen(self) -> None:
        self._close_time_zone_picker()
        self.fullscreen_camera = not self.fullscreen_camera
        self.canvas.yview_moveto(0)
        self._render_template()

    def _handle_escape(self) -> None:
        if self.time_zone_popup is not None:
            self._close_time_zone_picker()
        elif self.fullscreen_camera:
            self.toggle_camera_fullscreen()
        elif self.module_view:
            self._navigate("Overview")

    def _show_toast(self, message: str) -> None:
        """A concise, non-blocking confirmation for navigation and profile actions."""
        self.canvas.delete("toast")
        visible_top = self.canvas.canvasy(0)
        x = self.canvas.canvasx(self.canvas.winfo_width() / 2)
        y = visible_top + 30
        half_width = max(110, len(message) * 4.6)
        self.canvas.create_rectangle(x - half_width, y, x + half_width, y + 38, fill="#18294A", outline="#4C72A8", tags="toast")
        self.canvas.create_text(x, y + 19, text=message, fill="#FFFFFF", font=("Avenir Next", 12, "bold"), tags="toast")
        self.after(1900, lambda: self.canvas.delete("toast") if self.canvas.winfo_exists() else None)

    def start_camera(self) -> None:
        if cv2 is None or Image is None:
            messagebox.showinfo("Camera package needed", "Install camera support first:\n\npython3 -m pip install -r requirements.txt")
            return
        if self.camera_running:
            return
        camera, camera_index, first_frame = self._open_camera(
            (self.camera_index, 0, 1, 2)
        )
        if camera is None:
            messagebox.showerror(
                "Camera unavailable",
                "No usable camera frame was found.\n\n"
                "1. Close FaceTime, WhatsApp, Zoom, or any other app using the camera.\n"
                "2. In System Settings > Privacy & Security > Camera, allow Antigravity IDE or Python.\n"
                "3. Restart this dashboard and try Start Camera again.",
            )
            return
        self.camera = camera
        self.camera_index = camera_index
        self.pending_camera_frame = first_frame
        self.camera_running = True
        self.camera_failures = 0
        self.camera_frame_number = 0
        self.last_weapon_detections = []
        self.last_knife_detections = []
        self._render_template()
        self._show_toast(f"Camera {self.camera_index + 1} connected")
        self._show_frame()

    def _open_camera(self, candidate_indexes):
        """Open the first camera that can supply a real frame.

        AVFoundation is the stable OpenCV backend for macOS.  The fallback is
        retained for USB webcams and for non-macOS development environments.
        """
        if cv2 is None:
            return None, None, None

        unique_indexes = []
        for index in candidate_indexes:
            if index >= 0 and index not in unique_indexes:
                unique_indexes.append(index)

        backends = []
        if sys.platform == "darwin" and hasattr(cv2, "CAP_AVFOUNDATION"):
            backends.append(cv2.CAP_AVFOUNDATION)
        backends.append(cv2.CAP_ANY)

        for index in unique_indexes:
            used_backends = set()
            for backend in backends:
                if backend in used_backends:
                    continue
                used_backends.add(backend)
                capture = cv2.VideoCapture(index, backend)
                if not capture.isOpened():
                    capture.release()
                    continue
                # Some macOS backends open successfully but fail on the first
                # read when the camera is busy or permission has been revoked.
                okay, frame = capture.read()
                if okay and frame is not None:
                    return capture, index, frame
                capture.release()
        return None, None, None

    def _show_frame(self) -> None:
        if not self.camera_running or not self.camera:
            return
        if self.pending_camera_frame is not None:
            okay, frame = True, self.pending_camera_frame
            self.pending_camera_frame = None
        else:
            okay, frame = self.camera.read()
        if okay:
            self.camera_failures = 0
            if self.mirror_camera:
                frame = cv2.flip(frame, 1)
            self.camera_frame_number += 1
            # Ultralytics expects OpenCV's BGR ndarray.  Keep this conversion
            # after inference; PIL and the dashboard need RGB for display.
            if self.detector or self.knife_detector:
                frame = self._annotate_weapon_detections(frame)
            display_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.latest_frame = Image.fromarray(display_frame)
            if self.fullscreen_camera:
                self._render_fullscreen_camera()
                self.after(25, self._show_frame)
                return
            self._draw_live_frame()
        else:
            self.camera_failures += 1
            if self.camera_failures >= self.max_camera_failures:
                self._handle_camera_feed_failure()
                return
        self.after(25, self._show_frame)

    def _handle_camera_feed_failure(self) -> None:
        """Stop cleanly instead of silently showing an empty camera preview."""
        self.camera_running = False
        if self.camera:
            self.camera.release()
            self.camera = None
        self.pending_camera_frame = None
        self._render_template()
        messagebox.showerror(
            "Camera feed stopped",
            "The camera stopped sending frames. Close other camera apps, then click Start Camera again.",
        )

    def _annotate_weapon_detections(self, frame):
        """Combine project-model gun alerts with YOLO11n knife alerts locally."""
        evaluated = False
        if self.detector and self.camera_frame_number % self.detect_every_n_frames == 0:
            evaluated = True
            try:
                self.last_weapon_detections = self.detector.detect(frame)
            except Exception as error:
                print(f"Custom weapon detection skipped; it will retry: {error}")
                self.last_weapon_detections = []

        if self.knife_detector and self.camera_frame_number % self.knife_detect_every_n_frames == 0:
            evaluated = True
            try:
                self.last_knife_detections = self.knife_detector.detect(frame)
                self.people_count = getattr(self.knife_detector, "last_people_count", 0)
                self.vehicle_count = getattr(self.knife_detector, "last_vehicle_count", 0)
            except Exception as error:
                print(f"Knife detection skipped; it will retry: {error}")
                self.last_knife_detections = []

        has_threat = bool(self.last_weapon_detections or self.last_knife_detections)
        if has_threat and not self.threat_active:
            self.threat_active = True
            self.event_count += 1
            first_detection = (self.last_weapon_detections or self.last_knife_detections)[0]
            threat_name = first_detection.label.replace("_", " ").title()
            self._show_toast(f"⚠️ Security Alert: {threat_name} detected!")
        elif not has_threat and self.threat_active:
            self.threat_active = False

        if evaluated and not self.module_view and not self.fullscreen_camera and "stats" in self._layout and "risk" in self._layout:
            self._draw_stats_cards()
            self._draw_risk_card()

        for detection in self.last_weapon_detections:
            # OpenCV uses BGR. Bright Red for firearms / guns.
            self._draw_detection(frame, detection, (34, 38, 247))
        for detection in self.last_knife_detections:
            # Bright Orange/Amber for knives.
            self._draw_detection(frame, detection, (30, 160, 255))
        return frame

    @staticmethod
    def _draw_detection(frame, detection, color) -> None:
        x1, y1, x2, y2 = detection.box
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
        label = f"{detection.label.replace('_', ' ').upper()} {detection.confidence:.0%}"
        (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        top = max(24, y1)
        cv2.rectangle(frame, (x1, top - 22), (x1 + w + 8, top), color, -1)
        cv2.putText(
            frame,
            label,
            (x1 + 4, top - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    def stop_camera(self) -> None:
        self.camera_running = False
        if self.camera:
            self.camera.release()
            self.camera = None
        self.pending_camera_frame = None
        self.video_photo = None
        self.latest_frame = None
        self.last_weapon_detections = []
        self.last_knife_detections = []
        self.threat_active = False
        self.people_count = 0
        self.vehicle_count = 0
        self.fullscreen_camera = False
        self._render_template()

    def switch_camera(self) -> None:
        """Use the next available webcam; mirror the current feed if only one exists."""
        if not self.camera_running or not self.camera or cv2 is None:
            self.camera_index = 1 - self.camera_index
            self._show_toast(f"Camera {self.camera_index + 1} selected for the next start")
            return

        candidates = tuple((self.camera_index + offset) % 4 for offset in range(1, 4))
        candidate, candidate_index, first_frame = self._open_camera(candidates)
        if candidate is not None:
            self.camera.release()
            self.camera = candidate
            self.camera_index = candidate_index
            self.pending_camera_frame = first_frame
            self.camera_failures = 0
            self.mirror_camera = False
            self._show_toast(f"Switched to camera {candidate_index + 1}")
            return

        self.mirror_camera = not self.mirror_camera
        state = "mirrored" if self.mirror_camera else "normal"
        self._show_toast(f"Only one camera found — feed flipped to {state} view")

    def flip_camera(self) -> None:
        if not self.camera_running:
            return
        self.mirror_camera = not self.mirror_camera
        self._show_toast("Camera mirrored" if self.mirror_camera else "Camera orientation restored")

    def _close(self) -> None:
        self._close_time_zone_picker()
        self.camera_running = False
        if self.camera:
            self.camera.release()
        self.pending_camera_frame = None
        self.destroy()


def main(argv=None):
    """Launch the Sentinel Street dashboard."""
    SmartStreetLightApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
