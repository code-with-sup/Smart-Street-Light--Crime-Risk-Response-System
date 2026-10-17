import cv2
import numpy as np
from sentinel.detection import Detection
from sentinel.weapon_shape import analyze_mask, check_detections, inspect_crop


def blade_mask():
    mask = np.zeros((240, 140), np.uint8)
    cv2.fillPoly(mask, [np.array([(70, 15), (90, 130), (85, 220), (55, 220), (50, 130)])], 255)
    return mask


def scissors_mask():
    mask = np.zeros((260, 180), np.uint8)
    cv2.fillPoly(mask, [np.array([(70, 15), (102, 160), (147, 207), (130, 220), (85, 170), (44, 220), (30, 207), (75, 155)])], 255)
    for center in ((42, 213), (138, 213)):
        cv2.ellipse(mask, center, (27, 32), 0, 0, 360, 255, -1)
        cv2.ellipse(mask, center, (14, 20), 0, 0, 360, 0, -1)
    return mask


def test_blade_support_not_specific_knife_claim():
    result = analyze_mask(blade_mask())
    assert result['hint'] == 'blade-like'
    assert 'closed scissors' in result['reason']


def test_two_handle_loops_support_scissors():
    result = analyze_mask(scissors_mask())
    assert result['hint'] == 'scissors-like'
    assert result['features']['handle_holes'] == 2


def test_blank_tiny_and_clipped_are_uncertain():
    frame = np.zeros((200, 200, 3), np.uint8)
    assert inspect_crop(frame, (10, 10, 20, 30))['hint'] == 'uncertain'
    assert inspect_crop(frame, (10, 10, 150, 150))['hint'] == 'uncertain'
    mask = blade_mask(); mask[:30, 68:72] = 255
    assert analyze_mask(mask)['hint'] == 'uncertain'


def test_crop_and_disabled_preserve_yolo_decisions():
    mask = blade_mask()
    frame = np.full((*mask.shape, 3), 240, np.uint8)
    frame[mask > 0] = 30
    detection = Detection((45, 10, 95, 225), 'scissors', .8, 'weapon', source='test')
    gun = Detection((45, 10, 95, 225), 'handgun', .9, 'weapon')
    check_detections(frame, [detection, gun])
    assert detection.shape_check['hint'] == 'blade-like'
    assert (detection.label, detection.confidence, detection.category) == ('scissors', .8, 'weapon')
    assert gun.shape_check is None
    assert detection.as_dict()['shape_check'] is not None
    check_detections(frame, [detection], enabled=False)
    assert detection.shape_check is None


def test_setting_and_service_preserve_weapon_sos(service):
    service.update_settings({'weapon_shape_check': False})
    assert service.settings['weapon_shape_check'] is False
    detection = Detection((1, 1, 40, 45), 'knife', .9, 'weapon')
    service.detector.output = [detection]
    service._tick(0)
    assert detection.shape_check is None
    service.settings['weapon_shape_check'] = True
    service._tick(1)
    assert detection.shape_check['hint'] == 'uncertain'
    assert not service.notifier.sent
