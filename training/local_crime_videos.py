"""Experimental temporal classifier for filename-labeled local MP4 videos.

Video-level labels are weak; this model is never promoted to live SOS automatically.
"""
import argparse
import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path

ALIASES = {'pickpoketing': 'pickpocketing', 'peeing': 'public_urination',
           'normalvideos': 'normal', 'normalvideo': 'normal'}


def filename_label(path):
    name = re.sub(r'[\s_-]+', '', re.sub(r'\d+$', '', Path(path).stem.lower()))
    return ALIASES.get(name, name)


def prepare(source):
    import cv2
    groups, seen = defaultdict(list), {}
    for path in sorted(source.rglob('*')):
        if path.suffix.lower() != '.mp4':
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:
            raise ValueError(f'Duplicate source video: {path.name} and {seen[digest]}')
        seen[digest] = path.name
        cap = cv2.VideoCapture(str(path))
        count, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS)
        ok, frame = cap.read()
        cap.release()
        if not ok or count < 2 or fps <= 0:
            raise ValueError(f'Unreadable/empty video: {path}')
        groups[filename_label(path)].append({'file': str(path.relative_to(source)), 'sha256': digest,
            'frame_count': count, 'fps': fps, 'duration_seconds': count / fps})
    if len(groups) < 2:
        raise ValueError('At least two labeled classes are required')
    records = []
    rng = random.Random(42)
    for label, items in sorted(groups.items()):
        rng.shuffle(items)
        # Keep whole videos together. Never split neighboring frames across splits.
        for index, item in enumerate(items):
            split = 'test' if len(items) >= 2 and index == 0 else 'val' if len(items) >= 4 and index == 1 else 'train'
            records.append(dict(item, label=label, split=split))
    return {'classes': sorted(groups), 'videos': records,
            'warning': 'Filename labels describe whole videos, not every frame or event interval.'}


def main():
    import cv2
    import numpy as np
    import torch
    from PIL import Image
    from torchvision.models import ResNet18_Weights, resnet18
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--frames', type=int, default=32)
    parser.add_argument('--device', default='cpu')
    args = parser.parse_args()
    if args.frames < 2 or args.epochs < 1:
        parser.error('frames >= 2 and epochs >= 1 required')
    source = args.data.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = prepare(source)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print('Dataset:', {c: sum(v['label'] == c for v in manifest['videos']) for c in manifest['classes']}, flush=True)
    torch.manual_seed(42)
    torch.set_num_threads(4)
    weights = ResNet18_Weights.DEFAULT
    encoder = resnet18(weights=weights)
    encoder.fc = torch.nn.Identity()
    encoder.eval().to(args.device)
    transform = weights.transforms()
    cache = args.output / 'features'
    cache.mkdir(exist_ok=True)
    sequences = []
    for video in manifest['videos']:
        file = cache / f"{video['sha256']}-{args.frames}-resnet18.npy"
        if file.exists():
            seq = torch.from_numpy(np.load(file))
        else:
            cap = cv2.VideoCapture(str(source / video['file']))
            images = []
            for index in np.linspace(0, video['frame_count'] - 1, args.frames).astype(int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                ok, frame = cap.read()
                if not ok:
                    cap.release()
                    raise ValueError(f"Failed to decode {video['file']} at {index}")
                images.append(transform(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))))
            cap.release()
            with torch.inference_mode():
                seq = torch.cat([encoder(torch.stack(images[i:i + 8]).to(args.device)).cpu() for i in range(0, len(images), 8)])
            np.save(file, seq.numpy())
        sequences.append(seq)
        print('Encoded:', video['file'], video['split'], flush=True)
    del encoder
    x = torch.stack(sequences)
    classes = manifest['classes']
    y = torch.tensor([classes.index(v['label']) for v in manifest['videos']])
    masks = {s: torch.tensor([v['split'] == s for v in manifest['videos']]) for s in ('train', 'val', 'test')}
    mean = x[masks['train']].mean((0, 1))
    std = x[masks['train']].std((0, 1)).clamp_min(1e-6)
    x = ((x - mean) / std).to(args.device)
    y = y.to(args.device)
    gru = torch.nn.GRU(512, 64, batch_first=True).to(args.device)
    head = torch.nn.Sequential(torch.nn.Dropout(.5), torch.nn.Linear(64, len(classes))).to(args.device)
    parameters = list(gru.parameters()) + list(head.parameters())
    optimizer = torch.optim.AdamW(parameters, lr=.001, weight_decay=.05)
    counts = torch.bincount(y[masks['train']], minlength=len(classes)).float()
    criterion = torch.nn.CrossEntropyLoss(weight=(counts.sum() / (len(classes) * counts)).to(args.device))

    def predict(inputs):
        _, hidden = gru(inputs)
        return head(hidden[-1])

    def evaluate(split):
        gru.eval(); head.eval()
        indices = masks[split].nonzero().flatten()
        if not len(indices):
            return None
        with torch.inference_mode():
            predictions = predict(x[indices]).argmax(1).cpu()
        truth = y[indices].cpu()
        matrix = torch.zeros(len(classes), len(classes), dtype=torch.int64)
        for actual, predicted in zip(truth, predictions):
            matrix[actual, predicted] += 1
        support = matrix.sum(1)
        recalls = matrix.diag().float() / support.clamp_min(1)
        return {'videos': len(indices), 'accuracy': float((truth == predictions).float().mean()),
                'macro_recall_supported_classes': float(recalls[support > 0].mean()),
                'per_class_recall': {c: float(recalls[i]) if support[i] else None for i, c in enumerate(classes)},
                'confusion_matrix': matrix.tolist()}

    best = -float('inf')
    checkpoint = args.output / 'local-crime-video.pt'
    train_indices = masks['train'].nonzero().flatten()
    for epoch in range(args.epochs):
        gru.train(); head.train()
        optimizer.zero_grad()
        loss = criterion(predict(x[train_indices]), y[train_indices])
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, 1)
        optimizer.step()
        val = evaluate('val')
        score = val['macro_recall_supported_classes'] if val else -float(loss)
        if score > best:
            best = score
            torch.save({'gru': gru.state_dict(), 'head': head.state_dict(), 'mean': mean, 'std': std,
                        'classes': classes, 'frames': args.frames, 'encoder': 'resnet18_imagenet',
                        'hidden_size': 64, 'epoch': epoch + 1, 'validation': val}, checkpoint)
        if epoch == 0 or (epoch + 1) % 10 == 0:
            print(f'Epoch {epoch + 1}/{args.epochs}, loss={float(loss):.4f}, validation={val}', flush=True)
    saved = torch.load(checkpoint, map_location=args.device, weights_only=True)
    gru.load_state_dict(saved['gru']); head.load_state_dict(saved['head'])
    report = {'classes': classes, 'class_counts': {c: sum(v['label'] == c for v in manifest['videos']) for c in classes},
              'split_counts': {s: int(m.sum()) for s, m in masks.items()}, 'best_epoch': saved['epoch'],
              'validation': saved['validation'], 'test': evaluate('test'),
              'normal_videos_present': 'normal' in classes, 'live_sos_enabled': False,
              'limitations': ['Very small weakly labeled dataset; filename labels are unverified.',
                             'Classes with one video have no independent validation or test examples.',
                             'Not suitable for automatic alerts; include normal activity and unseen-camera evaluation.']}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2))
    print('Finished:', json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
