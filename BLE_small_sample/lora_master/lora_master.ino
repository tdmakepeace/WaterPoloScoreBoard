// LoRa master: USB serial from scoreboard app -> local display/buzzer + LoRa TX
// No BLE. Commands are handled here and relayed to remote scoreboard(s).
//
// Target board: Arduino Nano Every (testing) or Nano 33 BLE.
// - USB commands: Serial (PC COM port, 9600 baud)
// - LoRa module: Serial1 on pins 0 (RX1) and 1 (TX1)

#include "scoreboard_commands.h"

const unsigned long USB_BAUD = 9600;
const unsigned long LORA_BAUD = 9600;
const int LORA_AUX_PIN = -1;  // optional: digital pin wired to module AUX

void waitForUsbSerial(unsigned long timeoutMs) {
  unsigned long start = millis();
  while (!Serial && millis() - start < timeoutMs) {
  }
}

void forwardToLoRa(const String& command) {
  if (LORA_AUX_PIN >= 0) {
    unsigned long waitStart = millis();
    while (digitalRead(LORA_AUX_PIN) == LOW) {
      if (millis() - waitStart > 500) {
        break;
      }
    }
  }
  Serial1.println(command);
  Serial.print("LoRa TX: ");
  Serial.println(command);
}

void processUsbCommand(const String& rawLine) {
  String command = rawLine;
  command.trim();
  if (command.length() == 0) {
    return;
  }
  command = command.substring(0, 10);
  Serial.print("USB RX: ");
  Serial.println(command);

  // Drive this board's display and buzzer.
  handleScoreboardCommand(command, nullptr);

  // Relay the same command to other scoreboards over LoRa.
  forwardToLoRa(command);
}

void setup() {
  scoreboardSetupPins();

  Serial.begin(USB_BAUD);
  waitForUsbSerial(3000);

  // DX-LR02-433T22D on Serial1: module TX -> pin 0 (RX1), module RX -> pin 1 (TX1)
  Serial1.begin(LORA_BAUD);
  Serial1.setTimeout(20);

  Serial.println("LoRa master ready (USB serial -> local display + LoRa relay)");
}

void loop() {
  if (!Serial.available()) {
    return;
  }
  processUsbCommand(Serial.readStringUntil('\n'));
}
