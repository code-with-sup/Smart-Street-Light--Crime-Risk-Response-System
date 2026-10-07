"""Face blurring for privacy, using the face points the pose model already finds (nose, eyes, ears).

When those points are not visible (person seen from far away or from behind) the head is estimated
from the top of the person's box. Faces are pixelated, which is fast and cannot be reversed.
"""

from __future__ import annotations

import cv2
import numpy as np

from .detection import Detection

FACE_POINTS = (0, 1, 2, 3, 4)  # COCO: nose, left eye, right eye, left ear, right ear
MODES = ("off", "live", "everywhere")  # live = operator screen only; evidence keeps faces for police


def face_boxes(detections: list[Detection], frame_shape) -> list[tuple[int, int, int, int]]:
    h, w = frame_shape[:2]
    boxes = []
    for d in detections:
        if d.category != "person":
            continue
        x1, y1, x2, y2 = d.box
        bw, bh = x2 - x1, y2 - y1
        pts = None
        if d.keypoints is not None:
            visible = d.keypoints[list(FACE_POINTS)]
            visible = visible[visible[:, 2] > 0.4][:, :2]
            if len(visible):
                pts = visible
        if pts is not None:
            cx, cy = pts.mean(axis=0)
            span = max(float(np.ptp(pts[:, 0])) if len(pts) > 1 else 0.0, bw * 0.18, 12.0)
            half = span * 0.9
            fx1, fy1, fx2, fy2 = cx - half, cy - half * 1.2, cx + half, cy + half * 1.1
        else:  # no face points: the head is roughly the top sixth of a standing person
            fx1, fx2 = x1 + bw * 0.2, x2 - bw * 0.2
            fy1, fy2 = y1, y1 + min(bh * 0.18, bw * 0.8)
        box = (max(0, int(fx1)), max(0, int(fy1)), min(w, int(fx2)), min(h, int(fy2)))
        if box[2] - box[0] > 2 and box[3] - box[1] > 2:
            boxes.append(box)
    return boxes


def blur_faces(frame, detections: list[Detection]):
    """Return a copy of the frame with every detected person's face pixelated."""
    out = frame.copy()
    for x1, y1, x2, y2 in face_boxes(detections, frame.shape):
        region = out[y1:y2, x1:x2]
        small = cv2.resize(region, (max(1, (x2 - x1) // 12), max(1, (y2 - y1) // 12)), interpolation=cv2.INTER_LINEAR)
        out[y1:y2, x1:x2] = cv2.resize(small, (x2 - x1, y2 - y1), interpolation=cv2.INTER_NEAREST)
    return out
