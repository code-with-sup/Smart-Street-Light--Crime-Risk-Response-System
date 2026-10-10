"""Headless regression checks; never open a camera or location permission page."""

from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from smart_street_light import SmartStreetLightApp
from PIL import Image  # type: ignore[import-not-found]


class Canvas:
    def __init__(self, width, height):
        self.width, self.height, self.items = width, height, []
        self.cursor = ""

    def winfo_width(self): return self.width
    def winfo_height(self): return self.height
    def winfo_exists(self): return True
    def focus_set(self): pass
    def canvasx(self, x): return x
    def canvasy(self, y): return y
    def yview_moveto(self, fraction): pass
    def configure(self, **kwargs): self.cursor = kwargs.get("cursor", self.cursor)
    def tag_raise(self, tag): pass

    def _create(self, kind, args, kwargs):
        tags = kwargs.get("tags", ())
        if isinstance(tags, str): tags = (tags,)
        item = {"kind": kind, "coords": args, **kwargs, "tags": tags}
        self.items.append(item)
        return len(self.items)

    def create_text(self, *args, **kwargs): return self._create("text", args, kwargs)
    def create_image(self, *args, **kwargs): return self._create("image", args, kwargs)
    def create_rectangle(self, *args, **kwargs): return self._create("rectangle", args, kwargs)
    def create_oval(self, *args, **kwargs): return self._create("oval", args, kwargs)
    def create_line(self, *args, **kwargs): return self._create("line", args, kwargs)
    def create_arc(self, *args, **kwargs): return self._create("arc", args, kwargs)
    def create_polygon(self, *args, **kwargs): return self._create("polygon", args, kwargs)

    def find_withtag(self, tag): return [i for i in self.items if tag in i["tags"]]
    def delete(self, tag):
        self.items = [] if tag == "all" else [i for i in self.items if tag not in i["tags"]]
    def itemconfigure(self, tag, **kwargs):
        for item in self.find_withtag(tag): item.update(kwargs)
    def bbox(self, tag):
        items = self.find_withtag(tag)
        if not items: return None
        item = items[0]
        x, y = item["coords"]
        size = abs(item.get("font", ("",12))[1])
        width = len(item.get("text", ""))*size*.55
        return x-width/2,y-size/2,x+width/2,y+size/2


class Font:
    def __init__(self, *args, size=12, **kwargs): self.size = abs(size)
    def measure(self, text): return len(text)*self.size*.55
    def configure(self, size): self.size = abs(size)


def dashboard(width, height, dark=True):
    app = object.__new__(SmartStreetLightApp)
    app.canvas = Canvas(width, height)
    app.winfo_exists = lambda: True
    app.after = lambda *args: None
    app.dark_mode, app.module_view, app.active_nav = dark, None, "Overview"
    app.fullscreen_camera, app.camera_running = False, False
    app.detector = app.knife_detector = None
    app.latest_frame = app.video_photo = None
    app.time_zone_popup = None
    app.time_zone_buttons = {}
    app.time_zone_label, app.time_zone_name = app.TIME_ZONES[0]
    from zoneinfo import ZoneInfo
    app.time_zone = ZoneInfo(app.time_zone_name)
    app._clock_now = lambda: datetime(2026,10,5,17,45,tzinfo=timezone.utc).astimezone(app.time_zone)
    app.location = {"status":"awaiting_permission", "message":"Allow location."}
    app.location_service = SimpleNamespace(refresh=lambda:None,stop=lambda:None)
    app._last_cursor, app._layout = "", {}
    app._picker_actions, app._actions, app._ui_photos = [], [], []
    app.references = {
        mode: Image.open(app.ASSETS / f"dashboard-{mode}-reference.png").convert("RGB").crop((0,49,1655,950))
        for mode in ("dark","light")
    }
    app.scenes = {mode: img.crop((332,488,1151,735)) for mode,img in app.references.items()}
    return app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        photo = patch("smart_street_light.ImageTk.PhotoImage", side_effect=lambda img:img)
        font = patch("smart_street_light.tkfont.Font", Font)
        photo.start(); font.start()
        self.addCleanup(photo.stop); self.addCleanup(font.stop)

    def assert_controls_inside_screen(self, app):
        w,h = app._layout["width"], app._layout["height"]
        for name,(left,top,right,bottom),_ in app._actions+app._picker_actions:
            self.assertTrue(0 <= left < right <= w and 0 <= top < bottom <= h, (name,(left,top,right,bottom),(w,h)))

    def test_fit_and_controls_across_screens_and_themes(self):
        for width,height in ((1000,600),(1024,768),(1280,800),(1440,900),(1920,1080),(2560,1080),(1972,1280)):
            for dark in (True,False):
                with self.subTest(screen=(width,height), dark=dark):
                    app = dashboard(width,height,dark)
                    app._render_template()
                    self.assert_controls_inside_screen(app)
                    self.assertAlmostEqual(app._layout["height"]*app.scale_y,height)
                    self.assertAlmostEqual(app._layout["width"]*app.scale_x,width)
                    for view in ("Settings","GPS tracking","Incident review"):
                        app.module_view = view
                        app._render_template()
                        self.assert_controls_inside_screen(app)
                        self.assertFalse(app.canvas.find_withtag("live-camera"))

    def test_greeting_boundaries_and_selected_timezone(self):
        expected = {3:"Good evening",4:"Good morning",11:"Good morning",12:"Good afternoon",16:"Good afternoon",17:"Good evening",23:"Good evening"}
        for hour,text in expected.items(): self.assertEqual(SmartStreetLightApp._greeting(hour),text)
        app=dashboard(1440,900)
        app._render_template()
        self.assertEqual(app.canvas.find_withtag("greeting")[0]["text"],"Good evening,")
        app._set_time_zone("Los Angeles • PT","America/Los_Angeles")
        self.assertEqual(app.canvas.find_withtag("greeting")[0]["text"],"Good morning,")

    def test_hover_does_not_open_and_label_click_opens(self):
        app=dashboard(1280,800)
        app._render_template()
        item=app.canvas.find_withtag("clock-zone")[0]
        x,y=item["coords"]
        event=SimpleNamespace(x=x,y=y)
        for _ in range(30): app._on_hover(event)
        self.assertIsNone(app.time_zone_popup)
        app._on_click(event)
        self.assertIsNotNone(app.time_zone_popup)
        self.assert_controls_inside_screen(app)
        app._on_click(SimpleNamespace(x=300,y=20))
        self.assertIsNone(app.time_zone_popup)

    def test_settings_cards_choose_correct_zone(self):
        app=dashboard(1440,900)
        app.module_view="Settings"
        app._render_template()
        for index,(label,zone) in enumerate(app.TIME_ZONES):
            left,top,right,bottom=app._settings_time_zone_bounds(index)
            x,y=app._point((left+right)/2,(top+bottom)/2)
            app._on_click(SimpleNamespace(x=x,y=y))
            self.assertEqual(app.time_zone_name,zone)



if __name__ == "__main__":
    unittest.main()
