"""Background temporal predictions from the user's small video dataset.

Advisory output only: never feeds the risk engine, evidence recorder or SOS.
"""
from collections import deque
from pathlib import Path
import logging
import threading
import time

import cv2
import numpy as np

from .config import ROOT

log = logging.getLogger(__name__)
CHECKPOINT = ROOT / 'models' / 'video' / 'local-crime-video.pt'
WINDOW_SECONDS = 8.0
SAMPLE_SECONDS = .25
PREDICT_SECONDS = 4.0
STALE_SECONDS = 1.5


class CrimeVideoClassifier:
    def __init__(self, checkpoint=CHECKPOINT):
        self.checkpoint = Path(checkpoint)
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._frames = deque(maxlen=48)
        self._generation = 0
        self._last_sample = self._last_prediction = None
        self._prediction = None
        self._status = 'not_started'
        self._error = ''

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name='local-crime-video', daemon=True)
            self._thread.start()

    def stop(self):
        self.reset()
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=3)

    def reset(self):
        with self._lock:
            self._generation += 1
            self._frames.clear()
            self._last_sample = self._last_prediction = None
            self._prediction = None

    def observe(self, frame, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            if self._last_sample is not None and now - self._last_sample > STALE_SECONDS:
                self._generation += 1
                self._frames.clear()
                self._last_sample = self._last_prediction = None
                self._prediction = None
            if self._last_sample is not None and now - self._last_sample < SAMPLE_SECONDS:
                return
            height, width = frame.shape[:2]
            small = cv2.resize(frame, (max(1, round(width * 256 / height)), 256))
            self._frames.append((now, small))
            self._last_sample = now
        self._wake.set()

    def state(self, active=True, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            fresh = active and self._last_sample is not None and now - self._last_sample <= STALE_SECONDS
            span = self._frames[-1][0] - self._frames[0][0] if len(self._frames) > 1 else 0
            prediction = self._prediction if fresh else None
            return {'status': self._status if active else 'camera_off', 'ready': self._status == 'ready', 'error': self._error,
                    'buffer_seconds': round(span, 1) if fresh else 0,
                    'window_seconds': WINDOW_SECONDS, 'prediction': prediction,
                    'experimental': True, 'automatic_sos': False}

    def _job(self):
        with self._lock:
            if len(self._frames) < 2:
                return None
            now = self._frames[-1][0]
            if time.monotonic() - now > STALE_SECONDS or now - self._frames[0][0] < WINDOW_SECONDS:
                return None
            if self._last_prediction is not None and now - self._last_prediction < PREDICT_SECONDS:
                return None
            self._last_prediction = now
            frames = [frame for stamp, frame in self._frames if stamp >= now - WINDOW_SECONDS]
            return self._generation, now, frames

    def _publish(self, generation, stamp, prediction):
        with self._lock:
            if generation == self._generation and self._last_sample is not None and time.monotonic() - self._last_sample <= STALE_SECONDS:
                self._prediction = dict(prediction, sampled_at=stamp)

    def _load(self):
        import torch
        from torchvision.models import ResNet18_Weights, resnet18
        if not self.checkpoint.exists():
            raise FileNotFoundError('Local crime video checkpoint is not installed')
        saved = torch.load(self.checkpoint, map_location='cpu', weights_only=True)
        if saved['encoder'] != 'resnet18_imagenet' or saved['frames'] < 2:
            raise ValueError('Unsupported local crime checkpoint')
        self.classes, self.frame_count = saved['classes'], saved['frames']
        self.encoder = resnet18(weights=None)
        # Do not silently download a backbone at app startup.
        backbone = Path(torch.hub.get_dir()) / 'checkpoints' / 'resnet18-f37072fd.pth'
        self.encoder.load_state_dict(torch.load(backbone, map_location='cpu', weights_only=True))
        self.encoder.fc = torch.nn.Identity()
        self.encoder.eval()
        self.transform = ResNet18_Weights.DEFAULT.transforms()
        self.gru = torch.nn.GRU(512, saved['hidden_size'], batch_first=True).eval()
        self.head = torch.nn.Sequential(torch.nn.Dropout(.5), torch.nn.Linear(saved['hidden_size'], len(self.classes))).eval()
        self.gru.load_state_dict(saved['gru'])
        self.head.load_state_dict(saved['head'])
        self.mean, self.std = saved['mean'], saved['std']

    def _predict(self, frames):
        import torch
        from PIL import Image
        indices = np.linspace(0, len(frames) - 1, self.frame_count).astype(int)
        images = [self.transform(Image.fromarray(cv2.cvtColor(frames[i], cv2.COLOR_BGR2RGB))) for i in indices]
        with torch.inference_mode():
            vectors = torch.cat([self.encoder(torch.stack(images[i:i + 8])) for i in range(0, len(images), 8)])
            _, hidden = self.gru(((vectors - self.mean) / self.std).unsqueeze(0))
            scores = self.head(hidden[-1]).softmax(1)[0]
        ranked = sorted(zip(self.classes, scores.tolist()), key=lambda item: item[1], reverse=True)
        return {'label': ranked[0][0], 'score': round(ranked[0][1], 4),
                'alternatives': [{'label': label, 'score': round(score, 4)} for label, score in ranked[:3]]}

    def _run(self):
        try:
            with self._lock:
                self._status = 'loading'
            self._load()
            with self._lock:
                self._status = 'ready'
            while not self._stop.is_set():
                self._wake.wait(timeout=.5)
                self._wake.clear()
                job = self._job()
                if job:
                    generation, stamp, frames = job
                    self._publish(generation, stamp, self._predict(frames))
        except Exception as exc:
            log.exception('Local crime video classifier unavailable')
            with self._lock:
                self._status, self._error = 'error', str(exc)
                self._prediction = None
