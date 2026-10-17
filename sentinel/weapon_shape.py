"""Experimental classical-CV outline evidence on an existing weapon crop.

No trained classifier, no label overrides, and no change to risk/SOS decisions.
"""
import cv2
import numpy as np

ELIGIBLE = {'weapon', 'knife', 'scissors', 'sword', 'talwar', 'dagger', 'blade', 'razor', 'ustara', 'straight razor'}


def _uncertain(reason, **features):
    return {'hint': 'uncertain', 'reason': reason, 'features': features, 'method': 'contours', 'experimental': True}


def analyze_mask(mask):
    """Analyze a segmented silhouette; exposed separately for geometry tests."""
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return _uncertain('No usable outline')
    hierarchy = hierarchy[0]
    outer = [i for i, h in enumerate(hierarchy) if h[3] == -1]
    largest = max(outer, key=lambda i: cv2.contourArea(contours[i]))
    contour = contours[largest]
    area = cv2.contourArea(contour)
    fraction = area / mask.size
    if not .04 <= fraction <= .85:
        return _uncertain('Foreground too small or fills the crop')
    # Other large disconnected objects make outline-based reasoning unreliable.
    if any(i != largest and cv2.contourArea(contours[i]) > area * .2 for i in outer):
        return _uncertain('Multiple competing outlines')
    x, y, w, h = cv2.boundingRect(contour)
    if x <= 1 or y <= 1 or x + w >= mask.shape[1] - 1 or y + h >= mask.shape[0] - 1:
        return _uncertain('Outline cut off at crop boundary')
    sides = cv2.minAreaRect(contour)[1]
    elongation = max(sides) / max(1, min(sides))
    points = contour.reshape(-1, 2).astype(np.float32)
    mean, eigenvectors = cv2.PCACompute(points, mean=None)
    axis = eigenvectors[0]
    along = (points - mean) @ axis
    length = float(np.ptp(along))
    holes = []
    for i, relationship in enumerate(hierarchy):
        if relationship[3] != largest:
            continue
        hole = contours[i]
        hole_area = cv2.contourArea(hole)
        hx, hy, hw, hh = cv2.boundingRect(hole)
        if .012 * area <= hole_area <= .30 * area and min(hw, hh) >= 6 and hole_area / (hw * hh) > .45:
            moments = cv2.moments(hole)
            center = np.array([moments['m10'] / moments['m00'], moments['m01'] / moments['m00']])
            holes.append((hole_area, center))
    features = {'handle_holes': len(holes), 'elongation': round(elongation, 2), 'foreground_fraction': round(fraction, 2)}
    # Two similarly-sized enclosed loops located at one end support a scissors-like
    # silhouette. They do not prove scissors: unrelated objects may share this shape.
    if len(holes) == 2 and elongation >= 1.5:
        (a, ca), (b, cb) = holes
        position_a = float((ca - mean[0]) @ axis)
        position_b = float((cb - mean[0]) @ axis)
        if min(a, b) / max(a, b) >= .35 and position_a * position_b > 0 and abs(position_a - position_b) < length * .35:
            return {'hint': 'scissors-like', 'reason': 'Two enclosed handle-like loops at one end',
                    'features': features, 'method': 'contours', 'experimental': True}
    if not holes and elongation >= 3:
        perpendicular = np.array([-axis[1], axis[0]])
        across = (points - mean) @ perpendicular
        widths = []
        for low, high in ((.02, .18), (.30, .70), (.82, .98)):
            selected = across[(along >= along.min() + length * low) & (along <= along.min() + length * high)]
            widths.append(float(np.ptp(selected)) if len(selected) >= 2 else 0)
        if min(widths[0], widths[2]) > 0 and widths[1] > 4 and min(widths[0], widths[2]) < widths[1] * .6:
            return {'hint': 'blade-like', 'reason': 'Elongated outline with a tapered end; closed scissors can also match',
                    'features': features, 'method': 'contours', 'experimental': True}
    return _uncertain('No distinctive handle-loop or tapered-blade outline', **features)


def inspect_crop(frame, box):
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = map(int, box)
    bw, bh = x2 - x1, y2 - y1
    if min(bw, bh) < 24 or max(bw, bh) < 60:
        return _uncertain('Object crop too small')
    px, py = max(6, round(bw * .12)), max(6, round(bh * .12))
    left, top, right, bottom = max(0, x1 - px), max(0, y1 - py), min(width, x2 + px), min(height, y2 + py)
    if right <= left or bottom <= top:
        return _uncertain('Invalid crop')
    crop = frame[top:bottom, left:right]
    scale = min(1, 256 / max(crop.shape[:2]))
    if scale < 1:
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    if cv2.Laplacian(gray, cv2.CV_32F).var() < 8:
        return _uncertain('Crop blurry or lacks edge detail')
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB).astype(np.float32)
    border = np.concatenate((lab[:3].reshape(-1, 3), lab[-3:].reshape(-1, 3), lab[:, :3].reshape(-1, 3), lab[:, -3:].reshape(-1, 3)))
    background = np.median(border, axis=0)
    variation = np.linalg.norm(border - background, axis=1)
    if np.percentile(variation, 75) > 35:
        return _uncertain('Background too complex for silhouette extraction')
    distance = np.linalg.norm(lab - background, axis=2)
    diff = np.clip(distance, 0, 255).astype(np.uint8)
    threshold, _ = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = max(18, threshold, np.percentile(variation, 90) + 8)
    mask = (distance > threshold).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return analyze_mask(mask)


def check_detections(frame, detections, enabled=True):
    """Attach advisory metadata; never change labels, confidences or categories."""
    remaining = 4  # bounded CPU work even if several models produce duplicate boxes
    for detection in detections:
        detection.shape_check = None
        if enabled and remaining and detection.category == 'weapon' and detection.label.lower().replace('_', ' ') in ELIGIBLE:
            detection.shape_check = inspect_crop(frame, detection.box)
            remaining -= 1
