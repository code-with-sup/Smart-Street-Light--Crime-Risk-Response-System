/*
  Smart Street — ESP32 street light controller

  Board: ESP32 Dev Module (ESP32 Arduino core 3.x)
  Wiring:
    GPIO 25  street light LED (PWM, via transistor/MOSFET for bright loads)
    GPIO 26  piezo buzzer
    GPIO 27  PIR motion sensor OUT (HC-SR501)
    GPIO 34  LDR voltage divider (LDR to 3.3 V, 10k to GND; brighter = higher reading)
    GPIO 14  SOS push button to GND (internal pull-up; no resistor needed)

  Serial protocol, 115200 baud, one command per line:
    PC  -> ESP32   SET <brightness 0-100> <buzzer 0|1> [<strobe 0|1>]
                   CFG <ldr dark threshold 0-4095> <standalone dim % 0-100>
                   PING
    ESP32 -> PC    READY sentinel-esp32 v2
                   STATE <pir 0|1> <ldr 0-4095> <brightness> <buzzer> <strobe>   (every 500 ms)
                   SOS                     (the SOS button was pressed)
                   PONG

  Failsafe: if the dashboard sends nothing for 5 s, the light runs on its own:
  dark + motion -> 100 %, dark + no motion -> dim (20 % unless CFG says otherwise), daylight -> off.
  An SOS press with no dashboard strobes the lamp at full power and sounds the buzzer for 60 s.
*/

const int PIN_LED = 25;
const int PIN_BUZZER = 26;
const int PIN_PIR = 27;
const int PIN_LDR = 34;
const int PIN_SOS = 14;

const int PWM_FREQ = 5000;
const int PWM_BITS = 8;
int ldrDarkThreshold = 1500;  // updated by CFG from the dashboard
int standaloneDim = 20;       // %, updated by CFG
const unsigned long LINK_TIMEOUT_MS = 5000;
const unsigned long REPORT_EVERY_MS = 500;
const unsigned long STROBE_HALF_MS = 150;      // lamp on/off every 150 ms while strobing
const unsigned long SOS_DEBOUNCE_MS = 60;
const unsigned long SOS_LOCAL_MS = 60000;      // standalone SOS response length

int brightness = 0;       // 0-100 %
bool buzzer = false;
bool strobe = false;
unsigned long lastCommand = 0;
unsigned long lastReport = 0;
unsigned long sosUntil = 0;
bool sosLast = HIGH;
unsigned long sosChanged = 0;
String line;

void applyOutputs() {
  // while strobing, the lamp alternates between the requested brightness and off
  bool dark = strobe && ((millis() / STROBE_HALF_MS) % 2 == 1);
  ledcWrite(PIN_LED, dark ? 0 : map(brightness, 0, 100, 0, (1 << PWM_BITS) - 1));
  digitalWrite(PIN_BUZZER, buzzer ? HIGH : LOW);
}

void handleCommand(const String &cmd) {
  if (cmd.startsWith("SET ")) {
    int a = cmd.indexOf(' ', 4);
    if (a < 0) return;
    int b = cmd.indexOf(' ', a + 1);
    brightness = constrain(cmd.substring(4, a).toInt(), 0, 100);
    buzzer = cmd.substring(a + 1, b < 0 ? cmd.length() : b).toInt() == 1;
    strobe = b >= 0 && cmd.substring(b + 1).toInt() == 1;   // optional third value (v1 hosts omit it)
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
  pinMode(PIN_SOS, INPUT_PULLUP);
  analogReadResolution(12);
  ledcAttach(PIN_LED, PWM_FREQ, PWM_BITS);  // core 2.x: ledcSetup(0, PWM_FREQ, PWM_BITS); ledcAttachPin(PIN_LED, 0);
  applyOutputs();
  Serial.println("READY sentinel-esp32 v2");
}

void readSosButton() {
  bool now = digitalRead(PIN_SOS);
  if (now != sosLast && millis() - sosChanged > SOS_DEBOUNCE_MS) {
    sosChanged = millis();
    sosLast = now;
    if (now == LOW) {               // pressed (button pulls the pin to GND)
      Serial.println("SOS");
      sosUntil = millis() + SOS_LOCAL_MS;
    }
  }
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

  readSosButton();
  bool motion = digitalRead(PIN_PIR) == HIGH;
  int ldr = analogRead(PIN_LDR);

  // Standalone mode when the dashboard is not talking to us.
  if (millis() - lastCommand > LINK_TIMEOUT_MS) {
    if ((long)(sosUntil - millis()) > 0) {  // help requested and no dashboard (wrap-safe): make it impossible to miss
      brightness = 100; buzzer = true; strobe = true;
    } else {
      bool dark = ldr < ldrDarkThreshold;
      brightness = dark ? (motion ? 100 : standaloneDim) : 0;
      buzzer = false; strobe = false;
    }
  }
  applyOutputs();  // every loop, so the strobe keeps flashing

  if (millis() - lastReport >= REPORT_EVERY_MS) {
    lastReport = millis();
    Serial.printf("STATE %d %d %d %d %d\n", motion ? 1 : 0, ldr, brightness, buzzer ? 1 : 0, strobe ? 1 : 0);
  }
}
