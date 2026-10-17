from pathlib import Path
import pytest
from training.datasets import CLASSES, frame_identity, prepare_ucf, prepare_weapon, sample_frames


def test_video_identity_and_numeric_sampling():
    assert frame_identity('Normal_Videos_123_x264_20.png') == frame_identity('Normal_Videos123_x264_20.png')
    assert sample_frames(['Abuse001_x264_100.png','Abuse001_x264_2.png','Abuse001_x264_40.png'], 2) == ['Abuse001_x264_2.png','Abuse001_x264_100.png']
    with pytest.raises(ValueError):
        frame_identity('unrecognized.png')


def test_ucf_splits_whole_videos_and_detects_leakage(tmp_path):
    import json
    for split in ('Train', 'Test'):
        for label in CLASSES:
            folder = tmp_path / split / label
            folder.mkdir(parents=True)
            for video in range(3 if split == 'Train' else 1):
                for frame in (0, 10, 20):
                    (folder / f'{label}{split}{video}_x264_{frame}.png').touch()
    manifest = json.loads(prepare_ucf(tmp_path, tmp_path / 'out', 2).read_text())
    assert {r['split'] for r in manifest['videos']} == {'train', 'val', 'test'}
    assert len({r['video'] for r in manifest['videos']}) == len(manifest['videos'])
    assert all(len(r['frames']) == 2 for r in manifest['videos'])
    (tmp_path / 'Test/Abuse/AbuseTrain0_x264_0.png').touch()
    with pytest.raises(ValueError, match='leakage'):
        prepare_ucf(tmp_path, tmp_path / 'out')


def test_weapon_labels_and_cross_split_leakage(tmp_path):
    (tmp_path / 'data.yaml').write_text('names: [knife]\n')
    for index, split in enumerate(('train', 'valid', 'test')):
        for kind in ('images', 'labels'):
            (tmp_path / split / kind).mkdir(parents=True)
        (tmp_path / split / 'images/a.jpg').write_bytes(bytes([index]))
        (tmp_path / split / 'labels/a.txt').write_text('0 .5 .5 .2 .2\n')
    _, report = prepare_weapon(tmp_path, tmp_path / 'out')
    assert report['train']['boxes'] == {'knife': 1}
    (tmp_path / 'valid/labels/a.txt').write_text('1 .5 .5 .2 .2\n')
    with pytest.raises(ValueError, match='Out-of-range'):
        prepare_weapon(tmp_path, tmp_path / 'out')
    (tmp_path / 'valid/labels/a.txt').write_text('0 .5 .5 .2 .2\n')
    (tmp_path / 'valid/images/a.jpg').write_bytes(bytes([0]))
    with pytest.raises(ValueError, match='leakage'):
        prepare_weapon(tmp_path, tmp_path / 'out')


def test_ucf_training_writes_usable_checkpoint_and_held_out_report(tmp_path, monkeypatch):
    import argparse
    import json
    torch = pytest.importorskip('torch')
    torchvision = pytest.importorskip('torchvision')
    from PIL import Image
    from training.train_datasets import train_ucf

    class Encoder(torch.nn.Module):
        def forward(self, batch):
            return batch.mean((1, 2, 3)).unsqueeze(1).repeat(1, 512)

    monkeypatch.setattr(torchvision.models, 'resnet18', lambda **kwargs: Encoder())
    for split in ('Train', 'Test'):
        for cls, label in enumerate(CLASSES):
            folder = tmp_path / split / label
            folder.mkdir(parents=True)
            for video in range(2 if split == 'Train' else 1):
                for frame in (0, 10):
                    Image.new('RGB', (8, 8), (cls * 15, video * 50, frame)).save(folder / f'{label}{split}{video}_x264_{frame}.png')
    out = tmp_path / 'out'
    args = argparse.Namespace(ucf_data=tmp_path, output=out, frames_per_video=2, device='cpu', epochs=2)
    train_ucf(args)
    checkpoint = torch.load(out / 'ucf-video-baseline.pt', weights_only=True)
    assert checkpoint['mean'].shape == (1024,)
    assert checkpoint['classes'] == CLASSES
    report = json.loads((out / 'ucf-test.json').read_text())
    assert sum(map(sum, report['test']['confusion_matrix'])) == len(CLASSES)
    assert set(report['test']['per_class_recall']) == set(CLASSES)


def test_reference_set_does_not_silently_retrain_live_candidate(tmp_path):
    import argparse
    from training.train_datasets import train_weapon
    (tmp_path / 'curation.json').write_text('{"reference_only": true}')
    with pytest.raises(ValueError, match='small reference set'):
        train_weapon(argparse.Namespace(weapon_data=tmp_path))
