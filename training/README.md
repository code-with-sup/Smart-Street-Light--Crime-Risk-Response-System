# Local dataset training

The app already uses object-detection weights in `models/custom/`. Downloading a
new dataset does **not** retrain those weights. This workflow produces separate
candidate weights and held-out test reports; it never replaces the running model.

## Local data

- `Weapon-Detection/`: YOLO images/labels and `data.yaml` with
  the object classes listed in `reference_profile.json`. Preparation fixes stale dataset paths in a generated
  YAML, checks annotation ranges and missing labels, and rejects exact-image leakage.
- `ucf-crime/Train/<class>` and `ucf-crime/Test/<class>`: extracted UCF-Crime frames
  named `<video>_x264_<frame>.png`. All 14 class folders, including NormalVideos,
  are required. Frames are indexed by source video, sorted numerically, and sampled
  across its duration. A deterministic 20% of training videos per class becomes
  validation; the supplied Test split stays held out. Cross-split video overlap is
  rejected, including alternate Normal_Videos naming.

Raw datasets, generated absolute paths, logs, features and checkpoints are local,
ignored by Git. Obtain data separately and comply with its source license. The
local weapon export declares CC BY 4.0 in its original YAML; retain attribution.

## Commands (from project root)

```sh
.venv/bin/python -m pip install -r training/requirements.txt
.venv/bin/python -m training.train_datasets --task prepare
.venv/bin/python -m training.train_datasets --task ucf --device mps --epochs 100
.venv/bin/python -m training.train_datasets --task weapon --weapon-data /path/to/full/labeled-weapons --device mps --epochs 100
```

Use `--device cpu` without Apple Silicon, or an Ultralytics-compatible CUDA device
for weapons. For the UCF trainer use a PyTorch device such as `cuda:0`. Use
`--task weapon` / `--task ucf` to run separately. Paths can be overridden with
`--weapon-data`, `--ucf-data`, and `--output`. Default output: `runs/dataset-training`.
Re-running UCF reuses extracted features; delete that feature directory if source
images change in place. YOLO creates a new incremented run directory on each run.

Weapon training fine-tunes YOLO11n with boxes. `weapon-test.json` records test
metrics and the actual best-checkpoint path. The original local export had just
27 training, 4 validation and 9 test images; validation contained no knives or
shotguns. Its candidate was rejected after poor held-out evaluation and moved
to recoverable Trash. The local folder is now a curated set of 37 references,
including 13 firearm examples with source model names, tools and straight razor
(ustara). Katta is missing. See `reference_profile.json` for coverage. Most new
classes lack validation/test examples. Default weapon training refuses this
reference-only folder; `--allow-reference-training` explicitly enables small
experiments. Add diverse labeled examples and negative scenes before deployment.

UCF training uses an ImageNet-pretrained ResNet18 (downloaded on first use) as a
frozen frame encoder. Mean/max pooling across up to 32 sampled frames produces
one feature vector per video. A class-weighted classifier learns the 14 video
labels. Validation macro recall selects the checkpoint; `ucf-test.json` includes
held-out accuracy, macro/per-class recall and a confusion matrix. This lightweight
baseline uses every video, not every extracted frame; it does not model frame
order or locate when an event happens. `--frames-per-video` changes sampling.
It is not equivalent to a trained temporal action detector.

UCF labels are weak video-level labels. An anomalous video can contain many normal
frames. Do not convert these labels into YOLO boxes or claim every frame contains
a crime. Arrest and normal activity also require context, not automatic danger
classification. See the [official UCF project](https://www.crcv.ucf.edu/projects/real-world/)
and [Ultralytics training guide](https://docs.ultralytics.com/modes/train/).

## Using the results

Review the test reports and test representative local recordings, including pens,
curtains, boards and toys, before promoting weapon weights. The detector loads
YOLO **detection** checkpoints from `models/custom/` at startup. Keep previous
weights backed up outside that folder and install only the chosen replacement;
loading multiple weapon candidates together can duplicate/conflict detections.

`ucf-video-baseline.pt` is a separate PyTorch video classifier, **not a YOLO model**.
Keep it outside `models/custom/`. It is an offline experimental baseline and does
not drive SOS or live risk decisions. Live temporal inference and calibration
remain a separate step after evaluation demonstrates useful results.

## Class handling for future trained models

Scissors, bomb, talwar, katta, straight razor/ustara, and the 13 requested firearm
names are recognized by the app's class mapper **if a trained model emits them**.
Tools (hammer, screwdriver, ruler, sticks/rods) get ordinary tool boxes and do not
automatically trigger weapon alerts. The existing behavior detector can still
raise risk for observed violent actions. Reference images and aliases do not add
new capabilities to the retained checkpoint; retraining and evaluation are required.
