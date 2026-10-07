Drop Ultralytics YOLO .pt files here; they load automatically on start and all run together.
Classes are matched by name: gun/pistol/rifle/knife/weapon... -> weapon,
fight/violence/robbery/assault... -> crime event, "No Fight"/"Non-Violence"/"normal" -> calm
(shown in green, never raises the risk). Anything else (e.g. person, Bystander) is ignored.

weapon.pt: YOLO26s person/weapon, 416 px. Test split: weapon P 0.82 R 0.63 mAP50 0.69.
  Recommended weapon threshold 0.55 (72% of weapon frames, 4.9% false-alarm frames).

crime.pt: 9 classes (Violence, violent, Bystander, Gun, Man Holding Gun, Robbery Using Gun,
  No Fight, fight, knifes), 448 px, 60 epochs on crime_merged_640_yolo. Val P 0.62 R 0.55 mAP50 0.48.
  Its weapon classes use the weapon threshold; its crime classes use "Crime confidence".
  Test split (769 images), frame level:  thr 0.55 -> 65% of crime frames, 13% false alarms
                                         thr 0.65 -> 58% of crime frames,  7% false alarms (default)
  "Violence" is the noisiest class (it fired at 0.59 on a person sitting at a webcam).
