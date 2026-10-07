"""YOLO detection and tracking: people, vehicles and weapons, body pose, plus frame annotation.

- Generic COCO model (selectable size) finds people / vehicles / knives and tracks them (ByteTrack),
  so each person keeps an ID across frames.
- Custom models dropped into models/custom/*.pt (e.g. the trained person/weapon model) run alongside;
  their classes are mapped by name to weapons or crime events.
- A pose model adds 17 body keypoints to each tracked person for behaviour analysis (behavior.py).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

import re

import cv2
import numpy as np

from .config import CUSTOM_MODELS_DIR, CUSTOM_WEAPON_WEIGHTS, ROOT

log = logging.getLogger("sentinel.detection")

VEHICLES = {"bicycle", "car", "motorcycle", "bus", "truck"}
COCO_WEAPONS = {"knife", "scissors", "baseball bat"}
CUSTOM_RUNS = ("weapon_dataset_v1", "weapon_demo", "street_weapon_v1")

# Selectable generic models: bigger = more accurate (especially small objects like knives), slower.
MODELS = {
    "yolo11n": {"label": "YOLO11 nano — fastest", "size_mb": 6},
    "yolo11s": {"label": "YOLO11 small — balanced", "size_mb": 19},
    "yolo11m": {"label": "YOLO11 medium — most accurate", "size_mb": 39},
    "yolo26n": {"label": "YOLO26 nano — newest, fast", "size_mb": 6},
}
DEFAULT_MODEL = "yolo11n"
POSE_MODEL = "yolo11n-pose"

# How a custom model's class names map onto the app's categories.
WEAPON_WORDS = re.compile(r"gun|pistol|rifle|revolver|firearm|shotgun|shot-gun|smg|knife|dagger|blade|sword|machete|"
                          r"axe|weapon|blunt|grenade|bat\b(?!.*animal)", re.I)
EVENT_WORDS = re.compile(r"fight|violen|assault|robber|theft|steal|snatch|vandal|attack|punch|kick|shoot|fall", re.I)


def category_for(name: str) -> str | None:
    """weapon / event for a custom-model class name, or None to ignore it (e.g. person)."""
    if EVENT_WORDS.search(name):
        return "event"
    if WEAPON_WORDS.search(name):
        return "weapon"
    return None

# All GPU work goes through this lock. Metal (MPS) aborts the whole process if two threads encode
# commands at once, e.g. a new model warming up while the loop runs the old one.
GPU_LOCK = threading.Lock()

# OpenCV colours are BGR.
COLORS = {"person": (255, 170, 60), "vehicle": (120, 210, 40), "weapon": (40, 40, 235), "event": (0, 140, 255)}
SKELETON = ((5, 7), (7, 9), (6, 8), (8, 10), (5, 6), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16))


@dataclass
class Detection:
    box: tuple[int, int, int, int]
    label: str
    confidence: float
    category: str  # person | vehicle | weapon | event
    track_id: int | None = field(default=None)
    keypoints: np.ndarray | None = field(default=None, repr=False)  # (17, 3) x, y, conf for people
    source: str = ""

    def as_dict(self) -> dict:
        return {"box": self.box, "label": self.label, "confidence": round(self.confidence, 3),
                "category": self.category, "track_id": self.track_id, "source": self.source}


def _iou(a, b) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _pick_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:  # torch missing or broken backend: CPU still works
        pass
    return "cpu"


class _CustomModel:
    def __init__(self, yolo, label: str) -> None:
        self.yolo, self.label = yolo, label
        args = getattr(yolo, "ckpt", None) or {}
        self.imgsz = int((args.get("train_args") or {}).get("imgsz") or 640)  # predict at the trained size
        self.classes = {i: c for i, n in yolo.names.items() if (c := category_for(n))}


class Detector:
    def __init__(self, model: str = DEFAULT_MODEL, behaviour: bool = True) -> None:
        self.ready = False
        self.error = ""
        self.models: list[str] = []
        self.model_name = model if model in MODELS else DEFAULT_MODEL
        self.device = "cpu"
        self.tracking = False
        self._generic = None
        self._generic_classes: dict[int, str] = {}
        self._custom: list[_CustomModel] = []
        self._pose = None
        self.behaviour = behaviour
        try:
            self._load()
        except Exception as error:  # the dashboard still runs without detection
            self.error = f"Detection unavailable: {error}"
            log.exception("detector failed to load")

    def _load(self) -> None:
        from ultralytics import YOLO

        # Weights live in the project folder; Ultralytics downloads a missing official model there.
        weights = ROOT / f"{self.model_name}.pt"
        self._generic = YOLO(str(weights))
        wanted = {"person"} | VEHICLES | COCO_WEAPONS
        self._generic_classes = {i: n for i, n in self._generic.names.items() if n in wanted}
        self.models.append(weights.name)

        paths = sorted(CUSTOM_MODELS_DIR.glob("*.pt"))
        paths += [p for run in CUSTOM_RUNS if (p := CUSTOM_WEAPON_WEIGHTS / run / "weights" / "best.pt").exists()]
        for path in paths:
            try:
                custom = _CustomModel(YOLO(str(path)), path.name if path.parent == CUSTOM_MODELS_DIR else f"{path.parts[-3]}/best.pt")
            except Exception as error:
                log.warning("custom model %s not loaded: %s", path.name, error)
                continue
            if not custom.classes:
                log.warning("custom model %s has no weapon/crime classes (%s); skipped", path.name, list(custom.yolo.names.values()))
                continue
            self._custom.append(custom)
            self.models.append(custom.label)
        if self.behaviour:
            try:
                self._pose = YOLO(str(ROOT / f"{POSE_MODEL}.pt"))
                self.models.append(f"{POSE_MODEL}.pt")
            except Exception as error:
                log.warning("pose model not loaded, behaviour analysis off: %s", error)

        self.device = _pick_device()
        blank = np.zeros((320, 320, 3), dtype=np.uint8)
        with GPU_LOCK:
            models = [self._generic, *(c.yolo for c in self._custom), *([self._pose] if self._pose else [])]
            try:
                for model in models:
                    model.predict(blank, device=self.device, verbose=False)
            except Exception:
                log.warning("device %s failed warm-up, falling back to CPU", self.device)
                self.device = "cpu"
                for model in models:
                    model.predict(blank, device=self.device, verbose=False)
        try:
            import lap  # noqa: F401  (ByteTrack's assignment solver; avoids Ultralytics pip-installing at runtime)
            self.tracking = True
        except ImportError:
            log.warning("'lap' not installed: tracking off, loitering falls back to whole-scene timing")
        self.ready = True
        log.info("detector ready on %s: %s (tracking %s)", self.device, self.models, "on" if self.tracking else "off")

    def reset_tracks(self) -> None:
        """Forget track IDs (new camera / video), so IDs from the old scene are not carried over."""
        predictor = getattr(self._generic, "predictor", None)
        if predictor is not None and getattr(predictor, "trackers", None):
            for tracker in predictor.trackers:
                tracker.reset()

    def detect(self, frame, confidence: float, weapon_confidence: float) -> list[Detection]:
        if not self.ready:
            return []
        found: list[Detection] = []
        floor = min(confidence, weapon_confidence)
        options = dict(conf=floor, classes=list(self._generic_classes), device=self.device, verbose=False)
        with GPU_LOCK:
            if self.tracking:
                results = self._generic.track(frame, persist=True, tracker="bytetrack.yaml", **options)
            else:
                results = self._generic.predict(frame, **options)
            custom = [c.yolo.predict(frame, conf=weapon_confidence, imgsz=c.imgsz, classes=list(c.classes),
                                     device=self.device, verbose=False) for c in self._custom]
        for result in results:
            ids = result.boxes.id.int().tolist() if result.boxes.id is not None else [None] * len(result.boxes)
            for box, track_id in zip(result.boxes, ids, strict=True):
                name = self._generic_classes.get(int(box.cls[0]))
                score = float(box.conf[0])
                if name is None:
                    continue
                if name in COCO_WEAPONS:
                    category, needed = "weapon", weapon_confidence
                elif name == "person":
                    category, needed = "person", confidence
                else:
                    category, needed = "vehicle", confidence
                if score >= needed:
                    found.append(Detection(tuple(map(int, box.xyxy[0].tolist())), name, score, category, track_id))
        for model, model_results in zip(self._custom, custom, strict=True):
            for result in model_results:
                for box in result.boxes:
                    cls = int(box.cls[0])
                    found.append(Detection(tuple(map(int, box.xyxy[0].tolist())), model.yolo.names[cls],
                                           float(box.conf[0]), model.classes[cls], source=model.label))
        people = [d for d in found if d.category == "person"]
        if self._pose is not None and people:
            self._attach_pose(frame, people, confidence)
        return found

    def _attach_pose(self, frame, people: list[Detection], confidence: float) -> None:
        """Give each tracked person the keypoints of the pose skeleton that overlaps it most."""
        with GPU_LOCK:
            result = self._pose.predict(frame, conf=min(confidence, 0.3), device=self.device, verbose=False)[0]
        if result.keypoints is None or result.boxes is None or not len(result.boxes):
            return
        boxes = result.boxes.xyxy.cpu().numpy()
        kps = result.keypoints.data.cpu().numpy()  # (n, 17, 3)
        used = set()
        for person in people:
            best, best_iou = None, 0.5
            for i, box in enumerate(boxes):
                if i not in used and (iou := _iou(person.box, box)) > best_iou:
                    best, best_iou = i, iou
            if best is not None:
                used.add(best)
                person.keypoints = kps[best]


def annotate(frame, detections: list[Detection], events=()):
    """Draw pose skeletons and boxes on a copy; weapons and crime events get thick boxes so they stand out."""
    out = frame.copy()
    for det in detections:  # pose skeletons first, underneath the boxes
        if det.keypoints is not None:
            for a, b in SKELETON:
                if det.keypoints[a, 2] > 0.4 and det.keypoints[b, 2] > 0.4:
                    pa = tuple(int(v) for v in det.keypoints[a, :2])
                    pb = tuple(int(v) for v in det.keypoints[b, :2])
                    cv2.line(out, pa, pb, (230, 210, 120), 2, cv2.LINE_AA)
    for det in sorted(detections, key=lambda d: d.category in ("weapon", "event")):
        color = COLORS[det.category]
        x1, y1, x2, y2 = det.box
        thickness = 3 if det.category in ("weapon", "event") else 2
        cv2.rectangle(out, (x1, y1), (x2, y2), color, thickness)
        tag = f" #{det.track_id}" if det.track_id is not None else ""
        text = f"{det.label.upper()}{tag} {det.confidence:.0%}"
        (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        top = max(h + 8, y1)
        cv2.rectangle(out, (x1, top - h - 8), (x1 + w + 8, top), color, -1)
        cv2.putText(out, text, (x1 + 4, top - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    for event in events:  # crime behaviour: box around everyone involved, labelled at the bottom
        if not event.box:
            continue
        color = (40, 40, 235) if event.severity == "HIGH" else (0, 140, 255)
        x1, y1, x2, y2 = (int(v) for v in event.box)
        pad = 8
        cv2.rectangle(out, (x1 - pad, y1 - pad), (x2 + pad, y2 + pad), color, 3)
        text = event.label.split(" — ")[0].upper()
        (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(out, (x1 - pad, y2 + pad), (x1 - pad + w + 10, y2 + pad + h + 10), color, -1)
        cv2.putText(out, text, (x1 - pad + 5, y2 + pad + h + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    return out
