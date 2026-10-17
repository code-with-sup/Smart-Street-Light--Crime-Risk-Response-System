# Smart Street: ESP32 + PIR + LED + buzzer

Open `esp32_street_light.ino` in Arduino IDE. Select **ESP32 Dev Module**
for a classic ESP32-WROOM development board and install **esp32 by Espressif Systems,
version 2.x or 3.x** through Boards Manager. Select the USB port and Upload.
This sketch is for the classic ESP32, not an ESP32-C3 pin layout.

## Breadboard wiring

Disconnect USB power while changing wires. Read the labels on the components;
wire colours and header order alone do not establish pin functions.

| Component | Connection |
| --- | --- |
| HC-SR501 PIR VCC | ESP32 5V/VIN powered by USB |
| PIR OUT (red signal wire) | GPIO 27 |
| PIR GND | ESP32 GND |
| LED anode (long leg) | GPIO 26 through a 220/330 ohm resistor |
| LED cathode (short leg/flat side) | GND |
| Small active buzzer + | GPIO 4 |
| Buzzer - | GND |
| Breadboard ground rail | ESP32 GND |

All grounds must be connected. The HC-SR501 signal is normally 3.3V;
never connect a 5V output signal to an ESP32 GPIO. Use a transistor driver
for a buzzer or lamp that needs more current than a GPIO can supply.
The default is `ACTIVE_BUZZER = true`, matching the uploaded wiring guide.
For a passive piezo set it false; for an active-low module also set
`BUZZER_ACTIVE_HIGH = false`. For a three-pin module use its signal pin on GPIO4
and supply it at its rated voltage, with common ground.

## Behaviour

- **PIR motion response** in Sensors & lights enables or pauses PIR lighting.
  New installs start paused. Pausing does not disable weapon/crime alarms.
- Allow 60 seconds for sensor warm-up. Enabled PIR motion raises the LED to
  at least the configured dim level (20% by default). PIR movement does not
  sound the buzzer or send crime notifications/SOS.
- Camera weapon/crime alarms and manual buzzer tests control the buzzer separately.
  Buzzer output is held for at least 3 seconds; an ongoing threat can keep it on longer.
- Firmware remembers PIR enable/pause in ESP32 preferences. Manual tests
  temporarily pause PIR so that the selected test output can be checked.
- HC-SR501 sensitivity/hold time are adjusted on its physical potentiometers.
  PIR has no distance measurement; an exact close-only threshold needs a
  distance sensor. Reducing SENS may reduce range but cannot guarantee it.
- LDR / physical SOS remain disabled by default (GPIO34 / GPIO14).

## Connect to the project

Start the Python dashboard. In **Sensors & lights**, select the board's
USB serial port and connect. Close Arduino Serial Monitor first, because
it and Python cannot share the same port.

Serial Monitor at **115200 baud**, newline mode, can test these commands
(the uploaded 9600-baud setting does not match the current dashboard):

```text
SET 20 0 0
SET 100 0 0
SET 100 1 1
SET 20 0 0
PING
```

The commands set brightness, buzzer, and strobe. `PING` returns `PONG`.
PIR testing and USB commands do not require a camera or Telegram token.

PWM API reference: https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html

Manual aliases `L`, `M`, `H` also work in newline mode. Repeating the same
command reapplies its outputs. PIR never cancels a fresh HIGH command.
Firmware **v6** uses GPIO26 for the external LED, GPIO4 for the buzzer,
and GPIO27 for the PIR signal. It does not drive the built-in GPIO2 LED.
Re-upload this sketch after updating: changing the Python dashboard alone
cannot change pins in firmware already running on the ESP32.

## Current 30-row breadboard arrangement

This arrangement works on the smaller breadboard. Holes A–E in the same
numbered row connect internally; a different numbered row is a separate node.

| Part / wire | Exact connection |
| --- | --- |
| Resistor | E6 to E10 |
| LED long leg (+) | C10 |
| LED short leg (-) | C13 |
| White LED wire | ESP32 D26 to A6 |
| Yellow ground wire | ESP32 GND to B13 |
| Buzzer positive (check its + mark) | B19 |
| Buzzer negative | B22 |
| Blue buzzer signal wire | ESP32 D4 to any free A19–E19 hole, **not row 17** |
| Buzzer ground return | E22 to E13, joining the existing yellow GND |
| PIR red OUT wire | ESP32 D27 |
| PIR green GND wire | ESP32 GND |
| PIR brown VCC wire | ESP32 VIN/5V with USB power, **not 3V3** |

Remove the old buzzer return to an unconnected power rail when using the
direct E22-to-E13 ground jumper. A red/blue line is only a label: a rail is
not powered or grounded until a wire connects it. Match PIR labels rather
than relying only on wire colours. PIR input uses an internal pull-down so
a disconnected signal wire is less likely to report floating motion.

## What triggers the outputs

Confirmed weapon/crime detections request full LED and the independent
camera alarm. Model detections require two of the last three fresh passes;
sustained HIGH behaviour events also trigger it. Camera HIGH is held for
eight seconds after a threat. PIR motion does not activate the buzzer. The
camera alarm may continue when a crime threat is still present, even if PIR is paused.

Protocol: `SET <brightness> <camera-buzzer> [strobe]` controls host outputs.
`MOTION 0` / `MOTION 1` pauses/enables local PIR response independently.
`PING` returns firmware identity and `PONG`. Firmware v6 appends PIR-enabled
and legacy PIR-motion-window fields to each STATE report, after the original
fields. The legacy motion-window flag does not mean the buzzer is sounding.
