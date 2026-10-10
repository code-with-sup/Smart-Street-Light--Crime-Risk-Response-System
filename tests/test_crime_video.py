import numpy as np
from sentinel.crime_video import CrimeVideoClassifier


def test_sampling_and_reset_hide_old_prediction(monkeypatch):
    now = [0.0]
    monkeypatch.setattr('sentinel.crime_video.time.monotonic', lambda: now[0])
    model = CrimeVideoClassifier()
    frame = np.zeros((40, 60, 3), dtype=np.uint8)
    for index in range(33):
        now[0] = index / 4
        model.observe(frame)
    job = model._job()
    assert job is not None
    generation, stamp, _ = job
    model._publish(generation, stamp, {'label': 'robbery', 'score': .8})
    assert model.state()['prediction']['label'] == 'robbery'
    assert model.state(active=False)['prediction'] is None
    model.reset()
    model._publish(generation, stamp, {'label': 'robbery', 'score': .8})
    assert model.state()['prediction'] is None


def test_stall_resets_buffer_and_prediction(monkeypatch):
    now = [0.0]
    monkeypatch.setattr('sentinel.crime_video.time.monotonic', lambda: now[0])
    model = CrimeVideoClassifier()
    frame = np.zeros((40, 60, 3), dtype=np.uint8)
    model.observe(frame)
    model._publish(model._generation, 0, {'label': 'fighting', 'score': .9})
    now[0] = 2
    assert model.state()['prediction'] is None
    model.observe(frame)
    assert model.state()['buffer_seconds'] == 0
    assert model.state()['prediction'] is None
    assert model._job() is None


def test_predictions_never_enter_risk_or_send_sos(service):
    model = service.crime_video
    model._prediction = {'label': 'robbery', 'score': .99}
    service._tick(0)
    assert not service.notifier.sent
    assert not service.result.event
    assert not any(e.kind == 'local_crime_video' for e in service.events)
