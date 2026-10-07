# Sentinel Street — AI Smart Street Light with Crime-Risk Response

An AI + IoT street light that watches the street through a webcam, classifies the situation as
**LOW / MEDIUM / HIGH** risk, and responds: it dims or brightens the light, sounds a buzzer, saves
evidence, and alerts trusted contacts.

The camera feed is analysed **locally** with YOLO. Nothing leaves the computer unless you send an alert.

## Risk response

| Level | When | Street light | Buzzer | Recorded |
|---|---|---|---|---|
| **LOW** | Nobody around, or daytime with no crowd | Dim (20 %) at night, off by day | Off | — |
| **MEDIUM** | Person or PIR motion at night · crowd · someone lingering at night | 100 % | Off | Incident + snapshot |
| **HIGH** | Weapon seen in 2 of the last 3 detection passes, **or** a sustained crime behaviour (possible fight, person down, hands raised near someone) | 100 % | **On** | Incident + snapshot + alert |

HIGH is held for 8 s after the weapon leaves the frame so the light and buzzer don't flicker.
People are tracked (ByteTrack) so each keeps an ID; "lingering" is timed per person, and brief
detection dropouts (under 3 s) don't restart the timer.
All thresholds (confidence, crowd size, lingering time, night hours, dim level) are in **Settings**.

## Dashboard

| Tab | What it does |
|---|---|
| Overview | Live risk gauge, people/vehicle counts, light status, camera, activity, recent incidents |
| Live monitoring | Large feed, detector speed, confidence sliders, everything currently in view |
| Incident review | Every MEDIUM/HIGH event with snapshot; mark reviewed / false alarm, add notes, send alert, delete |
| GPS tracking | Map with the light's position (device location, pick on map, or typed) and incident pins; live tracking for mobile units |
| Alert contacts | Email / Telegram contacts, operator-confirm or automatic mode, test messages, delivery log |
| Sensors & lights | ESP32 connection, live PIR/LDR readings, light + buzzer state, manual test, wiring |
| Analytics | Incidents per day / hour / type, false-alarm rate, street activity over 24 h |
| Reports | PDF report (summary, log, evidence photos) or CSV for any date range |
| Settings | Time zone, detection, risk rules, lighting, alerts, evidence retention |

## Run it

Needs Python 3.10–3.12 (macOS, Windows or Linux).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

The landing page opens at http://127.0.0.1:8000 and the control room (dashboard) at http://127.0.0.1:8000/app.

**macOS camera permission:** run it from Terminal.app (or iTerm). On the first start, macOS asks
to allow the camera for your terminal; click Allow. The prompt has to come from the program's
main thread, so `run.py` asks once at startup before the server starts. If you denied it earlier,
turn it on in System Settings > Privacy & Security > Camera and restart. Apps that don't declare
camera use (some IDE / AI-tool terminals) are refused by macOS without a prompt; use Terminal.app.

Demo without a webcam (plays a video or image as the camera, loops forever):

```bash
.venv/bin/python run.py --video path/to/street.mp4
```

The server only listens on `127.0.0.1`, so the camera feed is not reachable from other machines.

## What it detects

| Source | Finds |
|---|---|
| Trained weapon model `models/custom/weapon.pt` (YOLO26s) | **weapons**: guns, rifles, knives, blunt objects |
| COCO model (YOLO11, selectable size) | people and vehicles (tracked with IDs), knives / scissors / bats |
| Pose model `yolo11n-pose.pt` | 17 body points per person, used for crime behaviour cues |

**Crime behaviour (pose rules, `sentinel/behavior.py`)**: each must persist briefly and is labelled "possible":
possible **fight** (two people in contact with fast repeated arm strikes) · **person down** (lying ≥ 2 s) ·
**hands raised near another person** (possible robbery) → HIGH; **several people running** → MEDIUM.
These are rules, not a trained crime classifier, so alerts wait for operator confirmation by default.
Switch them off in Settings > Detection.

**Weapon model accuracy** (684 held-out test images from its training dataset): weapon precision 0.82,
recall 0.63, mAP50 0.69. Per camera frame at the default weapon threshold **0.55**: 72 % of weapon
frames detected, 4.9 % false alarms on weapon-free frames; requiring 2 of 3 passes brings HIGH false
alarms to roughly 0.7 %. All three models together run at ~90 ms per frame on an M1 Pro.

**Your own models:** drop any Ultralytics `.pt` into `models/custom/`. Classes are matched by name:
gun / pistol / rifle / knife / weapon… become weapons; fight / violence / robbery / assault… become
crime events; anything else (e.g. person) is ignored. It runs at the image size it was trained at.

## AI model

Settings > Detection > **AI model** switches between YOLO11 nano (default, fastest), small, medium
and YOLO26 nano without restarting. Small/medium spot small objects such as knives noticeably better;
their weights download once (19 / 39 MB) into the project folder and are git-ignored. Measured on an
M-series Mac with tracking: nano ~45 ms, small ~60 ms per frame.

## Alerts (optional)

Alerts are **off until you configure them**, and by default the operator confirms each HIGH incident
before anyone is messaged (AI can mistake a phone or tool for a weapon). Switch to automatic in
*Alert contacts*.

1. `cp .env.example .env`
2. Fill in either channel:
   - **Email:** Gmail with an [App Password](https://myaccount.google.com/apppasswords) (`SMTP_*`).
   - **Telegram:** create a bot with @BotFather → `TELEGRAM_BOT_TOKEN`. Each contact presses *Start*
     on the bot once; their numeric chat ID comes from @userinfobot.
3. Restart, add contacts in the dashboard, press **Test**.

`.env` is git-ignored. Never commit real credentials.

## Hardware (ESP32)

Firmware: [`firmware/esp32_street_light/esp32_street_light.ino`](firmware/esp32_street_light/esp32_street_light.ino)
(Arduino IDE, board *ESP32 Dev Module*, ESP32 core 3.x).

| Part | ESP32 pin |
|---|---|
| Street light LED (PWM, via transistor/MOSFET) | GPIO 25 |
| Piezo buzzer | GPIO 26 |
| PIR sensor OUT (HC-SR501) | GPIO 27 |
| LDR divider (LDR → 3.3 V, 10 kΩ → GND) | GPIO 34 |

Plug the ESP32 in by USB and choose its port in **Sensors & lights**. Without a board the app runs a
simulator so everything else still works. If the dashboard stops talking to the ESP32 for 5 s, the
board falls back to standalone PIR + LDR lighting.

Serial protocol (115200 baud): PC sends `SET <brightness 0-100> <buzzer 0|1>`; the ESP32 replies
`STATE <pir> <ldr> <brightness> <buzzer>` every 500 ms.

## Project layout

```
run.py                 start server + open dashboard
sentinel/
  camera.py            webcam / video-file capture thread
  detection.py         YOLO detector (people, vehicles, weapons) + box drawing
  risk.py              LOW / MEDIUM / HIGH rules and light/buzzer response
  service.py           main loop: camera → AI → risk → hardware → incidents → alerts
  hardware.py          ESP32 serial link + simulator
  alerts.py            email / Telegram senders
  reports.py           PDF + CSV reports
  storage.py           SQLite (data/sentinel.db) + evidence images (data/evidence/)
  server.py            FastAPI REST API, MJPEG stream, WebSocket live state
web/                   landing page (three.js 3D hero) + dashboard (HTML/CSS/JS, Leaflet map, Chart.js)
web/models/            3D character + motion-capture rig for the landing page
firmware/              ESP32 sketch
tests/                 .venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest
                       (tests use a temporary data folder, never data/)
```

Custom gun-detection weights are picked up automatically from
`runs/weapon_detector/{weapon_dataset_v1,weapon_demo,street_weapon_v1}/weights/best.pt`.

## Landing page

`/` is a three.js night street: the Sentinel lamp, a person who walks in, draws a knife under the light,
and the AI response (light, alarm, detection boxes). `/?t=9` freezes the story at a given second,
handy for screenshots. Visitors with *reduce motion* switched on get a still frame.

Example detection images on the dashboard Overview (`web/showcase/`) come from the "Yolo Weapon
Detection" dataset (gsds-workspace, Roboflow Universe, CC BY 4.0), annotated by this app's own models.
The live camera and its snapshots appear only on Live monitoring and Incident review.

3D character credits: "Michelle" and the motion-capture source rig ("Vanguard", Walk/Idle/Run)
are Mixamo assets distributed with the three.js examples (MIT). The motion is retargeted onto the
character live in the browser. Any Mixamo character exported as GLB can replace
`web/models/human.glb`.

## Technology

Python · FastAPI · Ultralytics YOLO11 · OpenCV · SQLite · three.js · Leaflet + OpenStreetMap · Chart.js · ESP32 (Arduino)
