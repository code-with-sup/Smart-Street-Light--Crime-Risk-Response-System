"""Local dataset validation and video-level split preparation (no ML dependencies)."""
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

CLASSES = sorted('Abuse Arrest Arson Assault Burglary Explosion Fighting NormalVideos RoadAccidents Robbery Shooting Shoplifting Stealing Vandalism'.split())
IMAGES = {'.jpg', '.jpeg', '.png', '.bmp'}


def prepare_weapon(root, output):
    import yaml
    root, output = Path(root).resolve(), Path(output)
    config = yaml.safe_load((root / 'data.yaml').read_text())
    names = config['names']
    if isinstance(names, dict):
        names = [names[i] for i in range(len(names))]
    counts, hashes = {}, {}
    for split in ('train', 'valid', 'test'):
        images = sorted(p for p in (root / split / 'images').iterdir() if p.suffix.lower() in IMAGES)
        if not images:
            raise ValueError(f'No images in {split}')
        classes = Counter()
        for image in images:
            label = root / split / 'labels' / (image.stem + '.txt')
            if not label.exists():
                raise ValueError(f'Missing annotation: {label}')
            for line in label.read_text().splitlines():
                if not line.strip():
                    continue
                values = list(map(float, line.split()))
                if len(values) != 5 or not all(math.isfinite(x) for x in values):
                    raise ValueError(f'Invalid YOLO box: {label}')
                cls, x, y, w, h = values
                if cls != int(cls) or not 0 <= cls < len(names) or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                    raise ValueError(f'Out-of-range YOLO box: {label}')
                classes[names[int(cls)]] += 1
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            if digest in hashes and hashes[digest] != split:
                raise ValueError(f'Image leakage between {hashes[digest]} and {split}: {image}')
            hashes[digest] = split
        counts[split] = {'images': len(images), 'boxes': dict(classes), 'missing_classes': sorted(set(names) - classes.keys())}
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'weapon.yaml'
    target.write_text(yaml.safe_dump({'path': str(root), 'train': 'train/images', 'val': 'valid/images', 'test': 'test/images', 'names': names}))
    (output / 'weapon-report.json').write_text(json.dumps(counts, indent=2))
    return target, counts


def frame_identity(path):
    match = re.fullmatch(r'(.+)_x264_(\d+)', Path(path).stem)
    if not match:
        raise ValueError(f'Unknown UCF frame filename: {path}')
    return match[1].replace('_', '').lower(), int(match[2])


def sample_frames(frames, limit):
    frames = sorted(frames, key=lambda p: frame_identity(p)[1])
    if limit < 2:
        raise ValueError('At least two frames per video required')
    if len(frames) <= limit:
        return frames
    return [frames[round(i * (len(frames) - 1) / (limit - 1))] for i in range(limit)]


def prepare_ucf(root, output, frames_per_video=32):
    root, output = Path(root).resolve(), Path(output)
    records, seen = [], {}
    for source in ('Train', 'Test'):
        for label in CLASSES:
            folder = root / source / label
            if not folder.is_dir():
                raise ValueError(f'Missing class directory: {folder}')
            videos = defaultdict(list)
            for p in folder.iterdir():
                if p.suffix.lower() in IMAGES:
                    video, _ = frame_identity(p)
                    videos[video].append(str(p.relative_to(root)))
            if not videos:
                raise ValueError(f'No frames: {folder}')
            ids = sorted(videos, key=lambda v: hashlib.sha256(v.encode()).hexdigest())
            if source == 'Train' and len(ids) < 2:
                raise ValueError(f'Need at least two training videos for {label}')
            validation = set(ids[:max(1, round(len(ids) * .2))]) if source == 'Train' else set()
            for video in ids:
                if video in seen:
                    raise ValueError(f'Video leakage: {video} in {seen[video]} and {source}/{label}')
                seen[video] = f'{source}/{label}'
                records.append({'video': video, 'label': label, 'split': 'test' if source == 'Test' else ('val' if video in validation else 'train'), 'available_frames': len(videos[video]), 'frames': sample_frames(videos[video], frames_per_video)})
    output.mkdir(parents=True, exist_ok=True)
    manifest = output / 'ucf-videos.json'
    manifest.write_text(json.dumps({'root': str(root), 'classes': CLASSES, 'frames_per_video': frames_per_video, 'videos': records}, indent=2))
    return manifest
