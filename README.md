# Smart Street — AI Smart Street Light with Crime-Risk Response

An intelligent IoT and AI-based smart street light that improves public safety by detecting
suspicious activity and responding to different crime-risk levels.

A camera watches the street. YOLO-based computer vision finds **people, vehicles and weapons**, and
reads body pose for **crime behaviour** (a possible fight, a person down, hands raised near someone).
Every moment is classified as **LOW, MEDIUM or HIGH** risk, and the street light responds: it dims or
brightens the lamp, sounds a buzzer, saves evidence and alerts trusted contacts. An **ESP32** drives
the physical prototype (LED lamp, buzzer, PIR motion and LDR light sensors).

Video is analysed **on the computer itself**; nothing leaves it unless an alert is sent.

> **New here? Read [GUIDE.md](GUIDE.md).** It explains what was built, how to start it, and how every part works.

## Risk response

| Level | When | Street light | Buzzer | Recorded |
|---|---|---|---|---|
| **LOW** | Street clear | Dim (20 %) at night, off by day | Off | — |
| **MEDIUM** | Person or motion at night · crowd · someone lingering · several people running | 100 % | Off | Incident + snapshot |
| **HIGH** | Weapon confirmed (2 of 3 frames) · possible fight · person down · hands raised near someone · **SOS button** | 100 %, strobing | **On** | Incident + snapshot + clip + alert |

## Quick start

Needs **Python 3.10–3.12**.

**macOS / Linux**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py
```

The browser opens the landing page at **http://127.0.0.1:8000**. Click **Open control room**
(or go to **http://127.0.0.1:8000/app**), then press **Start camera**.

On macOS, run it from **Terminal.app** and click **Allow** when asked for camera access.
No webcam? Play a video as the camera: `run.py --video street.mp4`.

## Features

- 🎥 Live camera with AI boxes, person tracking IDs and pose skeletons
- 🔫 Weapon detection with the trained model `models/custom/weapon.pt` (YOLO26s)
- 🥊 Crime detection with the trained model `models/custom/crime.pt`: violence, fight, robbery with a gun ("No Fight" shown in green)
- 🧍 Crime-behaviour cues from body pose: possible fight, person down, possible robbery, people running
- 📊 LOW / MEDIUM / HIGH risk with clear reasons ("Weapon detected (68 %)", "Person #3 lingering 64 s")
- 💡 Lamp brightness and 🚨 buzzer driven over USB serial to the ESP32 (or a built-in simulator)
- 🌙 Day / night from the LDR sensor or the clock; 🚶 PIR motion at night
- 📸 Incidents saved with snapshot **and a 10-second video clip** (5 s before + 5 s after), review notes and false-alarm marking
- 🆘 **SOS button** on the pole: instant HIGH, lamp strobe, buzzer and an immediate alert (works even if the PC is down)
- ⚡ Lamp **strobes** while risk is HIGH
- 📐 **Zones & tripwires** drawn on the camera: no-entry areas, lingering areas, one-way tripwires, night-only schedules
- 🌡️ **Activity heatmap**: where people walk and linger, over a face-blurred view of the street
- 🔊 **Voice warning** from the speaker on HIGH (and optionally MEDIUM), with your own messages in any language
- 🙈 **Face blurring for privacy**: on the operator's screen only, or everywhere including evidence
- 🛡️ **Camera tamper detection**: covered / blinded (HIGH), blurred or turned away (MEDIUM)
- 🔋 **Energy report**: kWh, money and CO₂ saved by smart dimming vs a normal lamp
- ⏱️ **Alert escalation**: a HIGH alert nobody confirms within 5 min is sent automatically
- 📨 Email / Telegram alerts, confirmed by an operator by default
- 🗺️ GPS map of the light and incidents · 📈 analytics · 📄 PDF / CSV reports
- 🌐 Control-room dashboard (day / night themes, works on phones) and a 3D landing page

## Technology

**AI / vision:** Python, Ultralytics YOLO (YOLO11 tracking + pose, YOLO26s weapon model), OpenCV
**App:** FastAPI, WebSocket, SQLite, HTML/CSS/JS, three.js, Leaflet + OpenStreetMap, Chart.js
**Hardware:** ESP32 DevKitC, USB webcam, PIR sensor, LDR, LED, piezo buzzer (Arduino IDE)

## Project layout

```
run.py           start the server (and open the browser)
sentinel/        the Python service: camera, detection, behaviour, risk, hardware, alerts, storage, API
web/             dashboard (/app) and landing page (/)
models/custom/   trained models dropped here load automatically (weapon.pt, crime.pt)
firmware/        ESP32 sketch
tests/           automated tests (pip install -r requirements-dev.txt, then pytest)
GUIDE.md         full guide: setup, how it works, ESP32, alerts, retraining, troubleshooting
```

## Credits

- Weapon model trained on the "Yolo Weapon Detection" dataset (gsds-workspace, Roboflow Universe, CC BY 4.0);
  example images on the Overview come from its test split (`web/showcase/CREDITS.txt`).
- 3D character "Michelle" and motion rig "Vanguard": Mixamo assets shipped with the three.js examples (MIT).

## Training with local weapon and UCF-Crime data

Dataset validation, training commands, evaluation reports, and model deployment
limits are described in [training/README.md](training/README.md). Raw datasets and
training outputs remain local and are excluded from Git.
