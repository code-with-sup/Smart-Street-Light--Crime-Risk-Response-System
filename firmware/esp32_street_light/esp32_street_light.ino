/* Smart Street: classic ESP32-WROOM, PIR, breadboard LED and active buzzer.
 * GPIO26 -> 220/330 ohm resistor -> LED anode; LED cathode -> GND.
 * GPIO4 -> buzzer signal/+ (use a driver for higher-current buzzers); - -> GND.
 * HC-SR501: VCC -> 5V/VIN, GND -> GND, OUT -> GPIO27.
 * Serial 115200 baud, newline-terminated commands:
 * SET <brightness 0..100> <buzzer 0|1> [strobe 0|1], CFG <dark threshold> <dim %>, PING
 * Manual aliases: L = dim, M = full, H = full + buzzer.
 * MOTION 0|1 pauses/enables PIR response and persists across restarts.
 * PIR motion is silent and raises the LED to the configured dim level.
 * Motion never sends crime/SOS alerts; camera alarms remain independent.
 * Arduino ESP32 core 2.x and 3.x supported. Optional LDR/SOS disabled by default.
 */
#include <Arduino.h>
#include <esp_arduino_version.h>
#include <Preferences.h>
#include "motion_alarm.h"

const int PIN_LED = 26, PIN_BUZZER = 4, PIN_PIR = 27;
const int PIN_LDR = 34, PIN_SOS = 14;
const bool HAS_LDR = false, HAS_SOS_BUTTON = false;
const bool ACTIVE_BUZZER = true, BUZZER_ACTIVE_HIGH = true;
const int PWM_FREQ = 5000, PWM_BITS = 8, PWM_CHANNEL = 0;
const unsigned long LINK_TIMEOUT_MS = 5000, REPORT_EVERY_MS = 500;
const unsigned long PIR_WARMUP_MS = 60000, PIR_DEBOUNCE_MS = 250;
const unsigned long STROBE_HALF_MS = 150, SOS_DEBOUNCE_MS = 60, SOS_LOCAL_MS = 60000;
const unsigned long MIN_BUZZER_MS = 3000;
int brightness = 20, hostBrightness = 20, standaloneDim = 20, ldrDarkThreshold = 1500;
bool hostBuzzer = false, hostStrobe = false, pirEnabled = false;
Preferences preferences;
MotionAlarm motionAlarm;
void resolveOutputs();
bool buzzer = false, strobe = false, lastBuzzerOutput = false;
bool hostControl = false, motion = false, pirRaw = false, sosLast = HIGH;
bool overflow = false, localSos = false;
unsigned long lastCommand = 0, lastReport = 0, pirChanged = 0, sosChanged = 0, sosStarted = 0, buzzerUntil = 0;
String line;

void writeLamp(int duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_LED, duty);
#else
  ledcWrite(PWM_CHANNEL, duty);
#endif
}

void applyOutputs() {
  bool blank = strobe && ((millis() / STROBE_HALF_MS) % 2 == 1);
  writeLamp(blank ? 0 : map(brightness, 0, 100, 0, 255));
  bool output = buzzer;
  if (output != lastBuzzerOutput) {
    if (output) {
      if (ACTIVE_BUZZER) digitalWrite(PIN_BUZZER, BUZZER_ACTIVE_HIGH ? HIGH : LOW);
      else tone(PIN_BUZZER, 2700);
    } else {
      if (ACTIVE_BUZZER) digitalWrite(PIN_BUZZER, BUZZER_ACTIVE_HIGH ? LOW : HIGH);
      else noTone(PIN_BUZZER);
    }
    lastBuzzerOutput = output;
  }
}

void handleCommand(const String &cmd) {
  int a = 0, b = 0, c = 0; char extra;
  if (cmd.startsWith("SET ")) {
    int n = sscanf(cmd.c_str(), "SET %d %d %d %c", &a, &b, &c, &extra);
    if ((n != 2 && n != 3) || a < 0 || a > 100 || b < 0 || b > 1 || c < 0 || c > 1) return;
    // Ensure a trailing non-numeric token cannot be accepted as an optional value.
    String tail = cmd.substring(cmd.lastIndexOf(' ') + 1);
    if (tail != "0" && tail != "1") return;
    hostBrightness = a; hostBuzzer = b == 1; hostStrobe = n == 3 && c == 1;
    hostControl = true;
  } else if (cmd == "MOTION 0" || cmd == "MOTION 1") {
    bool enabled = cmd == "MOTION 1";
    if (pirEnabled != enabled) {
      pirEnabled = enabled;
      preferences.putBool("pir-enabled", pirEnabled);
    }
    motionAlarm.update(motion, pirEnabled, millis());
  } else if (cmd.startsWith("CFG ")) {
    if (sscanf(cmd.c_str(), "CFG %d %d %c", &a, &b, &extra) != 2 || a < 0 || a > 4095 || b < 0 || b > 100) return;
    ldrDarkThreshold = a; standaloneDim = b;
  } else if (cmd == "L" || cmd == "M" || cmd == "H") {
    hostBrightness = cmd == "L" ? standaloneDim : 100;
    hostBuzzer = cmd == "H"; hostStrobe = false; hostControl = true;
  } else if (cmd == "PING") {
    Serial.println("READY smart-street-esp32 v6");
    Serial.println("PONG");
  } else return;
  if (!cmd.startsWith("MOTION ")) lastCommand = millis();
  resolveOutputs();
  applyOutputs();
}

void setup() {
  Serial.begin(115200);
  preferences.begin("smart-street", false);
  pirEnabled = preferences.getBool("pir-enabled", false);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, ACTIVE_BUZZER && !BUZZER_ACTIVE_HIGH ? HIGH : LOW);
  pinMode(PIN_PIR, INPUT_PULLDOWN);
  if (HAS_SOS_BUTTON) pinMode(PIN_SOS, INPUT_PULLUP);
  if (HAS_LDR) analogReadResolution(12);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_LED, PWM_FREQ, PWM_BITS);
#else
  ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_BITS);
  ledcAttachPin(PIN_LED, PWM_CHANNEL);
#endif
  line.reserve(64);
  applyOutputs();
  Serial.println("READY smart-street-esp32 v6");
}

void readPir() {
  bool raw = digitalRead(PIN_PIR) == HIGH;
  if (raw != pirRaw) { pirRaw = raw; pirChanged = millis(); }
  motion = millis() < PIR_WARMUP_MS ? false :
      (millis() - pirChanged >= PIR_DEBOUNCE_MS ? pirRaw : motion);
}

void readSosButton() {
  if (!HAS_SOS_BUTTON) return;
  bool raw = digitalRead(PIN_SOS);
  if (raw != sosLast && millis() - sosChanged >= SOS_DEBOUNCE_MS) {
    sosChanged = millis(); sosLast = raw;
    if (raw == LOW) { Serial.println("SOS"); sosStarted = millis(); localSos = true; }
  }
}

void resolveOutputs() {
  bool hostFresh = hostControl && millis() - lastCommand <= LINK_TIMEOUT_MS;
  if (!hostFresh) hostControl = false;
  int ldr = HAS_LDR ? analogRead(PIN_LDR) : -1;
  bool dark = !HAS_LDR || ldr < ldrDarkThreshold;
  brightness = hostFresh ? hostBrightness : (dark ? standaloneDim : 0);
  bool dangerBuzzer = (hostFresh && hostBuzzer) || (!hostFresh && localSos);
  if (dangerBuzzer) {
    if (millis() >= buzzerUntil) buzzerUntil = millis() + MIN_BUZZER_MS;
  }
  buzzer = dangerBuzzer || (millis() < buzzerUntil);
  strobe = hostFresh && hostStrobe;
  if (!hostFresh && localSos) { brightness = 100; strobe = true; }
  motionAlarm.update(motion, pirEnabled, millis());
  if (pirEnabled && motion && brightness < standaloneDim) brightness = standaloneDim;
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      if (!overflow) { line.trim(); if (line.length()) handleCommand(line); }
      line = ""; overflow = false;
    } else if (c != '\r' && !overflow) {
      if (line.length() < 63) line += c;
      else { overflow = true; line = ""; }
    }
  }
  readPir(); readSosButton();
  int ldr = HAS_LDR ? analogRead(PIN_LDR) : -1;
  if (localSos && millis() - sosStarted >= SOS_LOCAL_MS) localSos = false;
  resolveOutputs();
  applyOutputs();
  if (millis() - lastReport >= REPORT_EVERY_MS) {
    lastReport = millis();
    Serial.printf("STATE %d %d %d %d %d %d %d\n", motion ? 1 : 0, ldr, brightness, buzzer ? 1 : 0, strobe ? 1 : 0, pirEnabled ? 1 : 0, motionAlarm.active() ? 1 : 0);
  }
}
