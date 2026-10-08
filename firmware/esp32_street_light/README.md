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
| PIR OUT | GPIO 5 |
| PIR GND | ESP32 GND |
| LED anode (long leg) | GPIO 2 through a 330 ohm resistor |
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

- Allow 60 seconds for the PIR to settle after power-up.
- Without the dashboard: no motion -> LED 20%; motion -> LED 100%.
  The buzzer stays off: motion alone does not establish a crime.
- With the dashboard: LOW/MEDIUM/HIGH controls LED brightness and buzzer.
  HIGH can strobe the LED. PIR state is returned every 500 milliseconds.
- If dashboard commands stop for five seconds, standalone PIR lighting resumes.
- LDR and physical SOS button are disabled by default. To add them, wire
  GPIO34 to an LDR divider and GPIO14 to a button to GND, then enable
  `HAS_LDR` / `HAS_SOS_BUTTON`. Without an LDR the dashboard uses its clock
  for day/night; the firmware sends -1 instead of a floating sensor reading.

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
The uploaded guide mentioned GPIO15 while its sketch used GPIO5; this version
consistently uses GPIO5. GPIO2 and GPIO5 are boot-strapping pins on classic
ESP32: if external devices prevent boot/upload, disconnect them during upload
or move them to GPIO25/GPIO27 and update the constants.
