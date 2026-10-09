"""Train local YOLO weapons and a weakly supervised UCF video baseline.

Run from the repository root: python -m training.train_datasets --task all
Outputs stay under ignored runs/dataset-training. Never auto-promotes models.
"""
import argparse
import json
import random
from pathlib import Path

from .datasets import prepare_ucf, prepare_weapon

ROOT = Path(__file__).resolve().parents[1]


def train_weapon(args):
    curation = Path(args.weapon_data) / 'curation.json'
    if curation.exists() and json.loads(curation.read_text()).get('reference_only') and not getattr(args, 'allow_reference_training', False):
        raise ValueError('This weapon folder is a small reference set, not a validated training dataset. Add diverse labeled examples or explicitly pass --allow-reference-training for experiments.')
    from ultralytics import YOLO
    data, report = prepare_weapon(args.weapon_data, args.output)
    print('Weapon dataset:', json.dumps(report), flush=True)
    model = YOLO(str(ROOT / 'yolo11n.pt'))
    model.train(data=str(data), epochs=args.epochs, imgsz=640, batch=8, device=args.device,
                workers=0, project=str(args.output), name='weapon', exist_ok=False,
                seed=42, patience=20, plots=True)
    best = Path(model.trainer.best)
    metrics = YOLO(str(best)).val(data=str(data), split='test', device=args.device, workers=0)
    (args.output / 'weapon-test.json').write_text(json.dumps({'checkpoint': str(best), 'metrics': metrics.results_dict, 'dataset': report}, indent=2))


def train_ucf(args):
    import numpy as np
    import torch
    from PIL import Image
    from torchvision.models import ResNet18_Weights, resnet18
    torch.manual_seed(42)
    random.seed(42)
    np.random.seed(42)
    manifest_path = prepare_ucf(args.ucf_data, args.output, args.frames_per_video)
    manifest = json.loads(manifest_path.read_text())
    weights = ResNet18_Weights.DEFAULT
    encoder = resnet18(weights=weights)
    encoder.fc = torch.nn.Identity()
    encoder = encoder.eval().to(args.device)
    transform = weights.transforms()
    cache = args.output / 'ucf-features'
    cache.mkdir(exist_ok=True)
    features, labels, splits = [], [], []
    # Each example is a whole video bag. Mean + max pool over chronological sampled
    # frames; labels describe videos, not every frame. This is not temporal localization.
    for index, video in enumerate(manifest['videos']):
        import hashlib
        key = hashlib.sha256(json.dumps({'root': manifest['root'], 'frames': video['frames'], 'encoder': str(weights)}, sort_keys=True).encode()).hexdigest()
        file = cache / f'{key}.npy'
        if file.exists():
            feature = np.load(file)
        else:
            encoded = []
            for start in range(0, len(video['frames']), 8):
                batch = []
                for name in video['frames'][start:start + 8]:
                    with Image.open(Path(manifest['root']) / name) as image:
                        batch.append(transform(image.convert('RGB')))
                with torch.inference_mode():
                    encoded.append(encoder(torch.stack(batch).to(args.device)).cpu())
            vectors = torch.cat(encoded)
            feature = torch.cat((vectors.mean(0), vectors.max(0).values)).numpy()
            np.save(file, feature)
        features.append(feature)
        labels.append(manifest['classes'].index(video['label']))
        splits.append(video['split'])
        if index % 10 == 0:
            print(f'UCF features {index + 1}/{len(manifest["videos"])} videos', flush=True)
    del encoder
    x, y = torch.tensor(np.stack(features)), torch.tensor(labels)
    masks = {split: torch.tensor([s == split for s in splits]) for split in ('train', 'val', 'test')}
    mean, std = x[masks['train']].mean(0), x[masks['train']].std(0).clamp_min(1e-6)
    x = (x - mean) / std
    model = torch.nn.Sequential(torch.nn.Linear(1024, 256), torch.nn.ReLU(), torch.nn.Dropout(.5), torch.nn.Linear(256, len(manifest['classes'])))
    counts = torch.bincount(y[masks['train']], minlength=len(manifest['classes'])).float()
    criterion = torch.nn.CrossEntropyLoss(weight=counts.sum() / (len(counts) * counts))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=.01)
    best_score = -1.0
    checkpoint = args.output / 'ucf-video-baseline.pt'

    def evaluate(split):
        model.eval()
        with torch.inference_mode():
            pred = model(x[masks[split]]).argmax(1)
        truth = y[masks[split]]
        matrix = torch.zeros((len(counts), len(counts)), dtype=torch.int64)
        for actual, predicted in zip(truth, pred):
            matrix[actual, predicted] += 1
        recall = matrix.diag().float() / matrix.sum(1).clamp_min(1)
        return {'accuracy': float((pred == truth).float().mean()), 'macro_recall': float(recall.mean()), 'per_class_recall': dict(zip(manifest['classes'], recall.tolist())), 'confusion_matrix': matrix.tolist()}

    for epoch in range(args.epochs):
        model.train()
        indices = masks['train'].nonzero().flatten()
        indices = indices[torch.randperm(len(indices))]
        for batch in indices.split(32):
            optimizer.zero_grad()
            loss = criterion(model(x[batch]), y[batch])
            loss.backward()
            optimizer.step()
        metrics = evaluate('val')
        print(f'UCF epoch {epoch + 1}/{args.epochs}: validation macro recall {metrics["macro_recall"]:.3f}', flush=True)
        if metrics['macro_recall'] > best_score:
            best_score = metrics['macro_recall']
            torch.save({'state_dict': model.state_dict(), 'mean': mean, 'std': std, 'classes': manifest['classes'], 'encoder': 'resnet18', 'weights': str(weights), 'pooling': 'mean_max', 'frames_per_video': args.frames_per_video, 'validation': metrics}, checkpoint)
    saved = torch.load(checkpoint, weights_only=True)
    model.load_state_dict(saved['state_dict'])
    (args.output / 'ucf-test.json').write_text(json.dumps({'checkpoint': str(checkpoint), 'validation': saved['validation'], 'test': evaluate('test'), 'warning': 'Weak video labels; experimental scene baseline, not crime localization or a YOLO detector.'}, indent=2))
    print('UCF training and held-out test evaluation finished.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', choices=['weapon', 'ucf', 'all', 'prepare'], default='all')
    parser.add_argument('--weapon-data', type=Path, default=ROOT / 'Weapon-Detection')
    parser.add_argument('--ucf-data', type=Path, default=ROOT / 'ucf-crime')
    parser.add_argument('--output', type=Path, default=ROOT / 'runs/dataset-training')
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--allow-reference-training', action='store_true', help='Explicitly allow experimental training on the curated reference set')
    parser.add_argument('--frames-per-video', type=int, default=32)
    parser.add_argument('--device', default='cpu', help='mps on Apple Silicon; cpu or CUDA device otherwise')
    args = parser.parse_args()
    if args.epochs < 1 or args.frames_per_video < 2:
        parser.error('epochs must be positive; frames-per-video must be >= 2')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.task == 'prepare':
        print(prepare_weapon(args.weapon_data, args.output)[1], flush=True)
        path = prepare_ucf(args.ucf_data, args.output, args.frames_per_video)
        records = json.loads(path.read_text())['videos']
        print({split: sum(r['split'] == split for r in records) for split in ('train', 'val', 'test')}, flush=True)
        return
    if args.task in ('weapon', 'all'):
        train_weapon(args)
    if args.task in ('ucf', 'all'):
        train_ucf(args)


if __name__ == '__main__':
    main()
