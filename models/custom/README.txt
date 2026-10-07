Drop Ultralytics YOLO .pt files here; they load automatically on start.
Classes are matched by name: gun/pistol/rifle/knife/weapon... -> weapon,
fight/violence/robbery/assault... -> crime event. Anything else (e.g. person) is ignored.
weapon.pt: YOLO26s person/weapon, 416 px. Test split: weapon P 0.82 R 0.63 mAP50 0.69.
Recommended weapon threshold 0.55 (72% of weapon frames, 4.9% false-alarm frames).
