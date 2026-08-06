// Passthrough USB Serial <-> LoRa module Serial1 for AT configuration.
// Wiring: LoRa on Serial1 pins 0 (RX) / 1 (TX). For config mode tie M0=LOW, M1=HIGH.
// Open Serial Monitor at 9600, line ending CR+LF, type AT commands directly.

const unsigned long LORA_BAUD = 9600;

void setup() {
  Serial.begin(9600);
  while (!Serial) {
  }
  Serial1.begin(LORA_BAUD);
  Serial.println("LoRa config passthrough ready (9600)");
}

void loop() {
  while (Serial.available()) {
    Serial1.write(Serial.read());
  }
  while (Serial1.available()) {
    Serial.write(Serial1.read());
  }
}
