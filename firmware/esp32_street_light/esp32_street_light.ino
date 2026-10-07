/*
  Sentinel Street — ESP32 street light controller

  Board: ESP32 Dev Module (ESP32 Arduino core 3.x)
  Wiring:
    GPIO 25  street light LED (PWM, via transistor/MOSFET for bright loads)
    GPIO 26  piezo buzzer
    GPIO 27  PIR motion sensor OUT (HC-SR501)
    GPIO 34  LDR voltage divider (LDR to 3.3 V, 10k to GND; brighter = higher reading)

  Serial protocol, 115200 baud, one command per line:
    PC  -> ESP32   SET <brightness 0-100> <buzzer 0|1>
                   CFG <ldr dark threshold 0-4095> <standalone dim % 0-100>
                   PING
    ESP32 -> PC    READY sentinel-esp32 v1
                   STATE <pir 0|1> <ldr 0-4095> <brightness> <buzzer>   (every 500 ms)
                   PONG

  Failsafe: if the dashboard sends nothing for 5 s, the light runs on its own:
  dark + motion -> 100 %, dark + no motion -> dim (20 % unless CFG says otherwise), daylight -> off,
  buzzer off. "Dark" uses the threshold from CFG, so it matches the dashboard's setting.
*/

const int PIN_LED = 25;
const int PIN_BUZZER = 26;
const int PIN_PIR = 27;
const int PIN_LDR = 34;

const int PWM_FREQ = 5000;
const int PWM_BITS = 8;
int ldrDarkThreshold = 1500;  // updated by CFG from the dashboard
int standaloneDim = 20;       // %, updated by CFG
const unsigned long LINK_TIMEOUT_MS = 5000;
const unsigned long REPORT_EVERY_MS = 500;

int brightness = 0;       // 0-100 %
bool buzzer = false;
unsigned long lastCommand = 0;
unsigned long lastReport = 0;
String line;

void applyOutputs() {
  ledcWrite(PIN_LED, map(brightness, 0, 100, 0, (1 << PWM_BITS) - 1));
  digitalWrite(PIN_BUZZER, buzzer ? HIGH : LOW);
}

void handleCommand(const String &cmd) {
  if (cmd.startsWith("SET ")) {
    int space = cmd.indexOf(' ', 4);
    if (space < 0) return;
    brightness = constrain(cmd.substring(4, space).toInt(), 0, 100);
    buzzer = cmd.substring(space + 1).toInt() == 1;
    lastCommand = millis();
    applyOutputs();
  } else if (cmd.startsWith("CFG ")) {
    int space = cmd.indexOf(' ', 4);
    if (space < 0) return;
    ldrDarkThreshold = constrain(cmd.substring(4, space).toInt(), 0, 4095);
    standaloneDim = constrain(cmd.substring(space + 1).toInt(), 0, 100);
    lastCommand = millis();
  } else if (cmd == "PING") {
    lastCommand = millis();
    Serial.println("PONG");
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_PIR, INPUT);
  analogReadResolution(12);
  ledcAttach(PIN_LED, PWM_FREQ, PWM_BITS);  // core 2.x: ledcSetup(0, PWM_FREQ, PWM_BITS); ledcAttachPin(PIN_LED, 0);
  applyOutputs();
  Serial.println("READY sentinel-esp32 v1");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      line.trim();
      if (line.length()) handleCommand(line);
      line = "";
    } else if (line.length() < 64) {
      line += c;
    }
  }

  bool motion = digitalRead(PIN_PIR) == HIGH;
  int ldr = analogRead(PIN_LDR);

  // Standalone mode when the dashboard is not talking to us.
  if (millis() - lastCommand > LINK_TIMEOUT_MS) {
    bool dark = ldr < ldrDarkThreshold;
    int wanted = dark ? (motion ? 100 : standaloneDim) : 0;
    if (wanted != brightness || buzzer) {
      brightness = wanted;
      buzzer = false;
      applyOutputs();
    }
  }

  if (millis() - lastReport >= REPORT_EVERY_MS) {
    lastReport = millis();
    Serial.printf("STATE %d %d %d %d\n", motion ? 1 : 0, ldr, brightness, buzzer ? 1 : 0);
  }
}
