"""Face blurring: where faces are found, and which outputs get blurred in each mode."""

import numpy as np

from sentinel.detection import Detection
from sentinel.privacy import blur_faces, face_boxes


def textured(h=400, w=400):
    return np.random.default_rng(1).integers(0, 255, (h, w, 3), dtype=np.uint8)


def person_with_face(nose=(200, 80)):
    k = np.zeros((17, 3))
    k[0] = (*nose, 0.9)                                 # nose
    k[1], k[2] = (nose[0] - 8, nose[1] - 6, 0.9), (nose[0] + 8, nose[1] - 6, 0.9)  # eyes
    k[3], k[4] = (nose[0] - 18, nose[1], 0.8), (nose[0] + 18, nose[1], 0.8)        # ears
    return Detection((150, 50, 250, 380), "person", 0.9, "person", 1, k)


def test_face_box_comes_from_face_keypoints():
    (x1, y1, x2, y2), = face_boxes([person_with_face()], (400, 400, 3))
    assert x1 < 200 < x2 and y1 < 80 < y2 and (x2 - x1) < 100  # around the nose, much smaller than the body


def test_without_keypoints_the_top_of_the_box_is_used():
    d = Detection((100, 100, 200, 400), "person", 0.9, "person", 1)
    (x1, y1, x2, y2), = face_boxes([d], (500, 500, 3))
    assert y1 == 100 and y2 <= 160 and 100 < x1 < x2 < 200


def test_blur_changes_only_the_face():
    frame = textured()
    out = blur_faces(frame, [person_with_face()])
    (x1, y1, x2, y2), = face_boxes([person_with_face()], frame.shape)
    assert not np.array_equal(out[y1:y2, x1:x2], frame[y1:y2, x1:x2])
    assert np.array_equal(out[300:, :], frame[300:, :])  # the rest of the picture untouched


def test_modes_blur_live_view_or_evidence(service):
    from sentinel.detection import annotate

    frame = textured()
    people = [person_with_face()]
    plain = annotate(frame, people, [])  # boxes and skeletons, faces untouched
    service.settings = service.store.save_settings({"blur_faces": "live"})
    assert not np.array_equal(service._overlay(frame, people, []), plain)               # operator screen: blurred
    assert np.array_equal(service._overlay(frame, people, [], evidence=True), plain)    # evidence: faces kept
    service.settings = service.store.save_settings({"blur_faces": "everywhere"})
    assert not np.array_equal(service._overlay(frame, people, [], evidence=True), plain)
    service.settings = service.store.save_settings({"blur_faces": "off"})
    assert np.array_equal(service._overlay(frame, people, []), plain)
