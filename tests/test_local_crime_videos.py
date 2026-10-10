from pathlib import Path

import cv2
import numpy as np
import pytest

from training.local_crime_videos import filename_label, prepare


def write_video(path, seed):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'mp4v'), 10, (32, 32))
    for value in range(5):
        writer.write(np.full((32, 32, 3), seed + value * 10, dtype=np.uint8))
    writer.release()


def test_filename_aliases():
    assert filename_label(Path('Theft5.mp4')) == 'theft'
    assert filename_label(Path('pickpoketing1.mp4')) == 'pickpocketing'
    assert filename_label(Path('peeing.mp4')) == 'public_urination'
    assert filename_label(Path('Normal_Videos3.mp4')) == 'normal'


def test_whole_video_splits_and_singleton_coverage(tmp_path):
    for index in range(5):
        write_video(tmp_path / f'theft{index}.mp4', index * 20)
    write_video(tmp_path / 'fighting.mp4', 150)
    manifest = prepare(tmp_path)
    theft = [v for v in manifest['videos'] if v['label'] == 'theft']
    assert sorted(v['split'] for v in theft) == ['test', 'train', 'train', 'train', 'val']
    fight = [v for v in manifest['videos'] if v['label'] == 'fighting']
    assert fight[0]['split'] == 'train'
    assert len({v['sha256'] for v in manifest['videos']}) == 6
    assert prepare(tmp_path) == manifest


def test_duplicate_sources_rejected(tmp_path):
    write_video(tmp_path / 'theft1.mp4', 1)
    (tmp_path / 'robbery.mp4').write_bytes((tmp_path / 'theft1.mp4').read_bytes())
    with pytest.raises(ValueError, match='Duplicate source video'):
        prepare(tmp_path)
