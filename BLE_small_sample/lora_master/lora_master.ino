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

// ---------------------------------------------------------------------------
// LoRa CHANNEL CONFIGURATION (same table as remote)
// ---------------------------------------------------------------------------
// The DX-LR32 uses frequencies, not numbered channels.
// We define our own channel table for convenience.
//
// To change the LoRa channel later, simply edit LORA_DEFAULT_CHANNEL below.
// ---------------------------------------------------------------------------

const long LORA_CHANNEL_FREQS[] = {
  433050000,  // CH0
  433100000,  // CH1
  433150000,  // CH2
  433200000   // CH3
};

const uint8_t LORA_CHANNEL_COUNT =
    sizeof(LORA_CHANNEL_FREQS) / sizeof(long);

// ---------------------------------------------------------------------------
// SELECT WHICH CHANNEL THIS MASTER SHOULD USE
// ---------------------------------------------------------------------------
// Change this number to switch channel:
//   0 = 433.050 MHz
//   1 = 433.100 MHz
//   2 = 433.150 MHz
//   3 = 433.200 MHz
//
// Example: set to channel 2 → 433.150 MHz
// ---------------------------------------------------------------------------
const uint8_t LORA_DEFAULT_CHANNEL = 2;

// Pool link: ~30 m, over water, bodies in the path. Must match the remote.
const uint8_t LORA_SPREAD_FACTOR = 7;   // SF5–12; 7 = fast, plenty for 30 m
const uint8_t LORA_TX_POWER_DBM  = 22;  // 0–22 dBm; 22 = max punch through bodies

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

void forwardLoRaAT(const String& cmd) {
  Serial1.println(cmd);
  Serial.print("LoRa AT: ");
  Serial.println(cmd);
}

void setLoRaChannel(uint8_t ch) {
  if (ch >= LORA_CHANNEL_COUNT) {
    Serial.print("Invalid LoRa channel: ");
    Serial.println(ch);
    return;
  }

  long freq = LORA_CHANNEL_FREQS[ch];
  String cmd = "AT+FREQ=" + String(freq);

  Serial.print("Setting LoRa channel ");
  Serial.print(ch);
  Serial.print(" (");
  Serial.print(freq);
  Serial.println(" Hz)");

  forwardLoRaAT(cmd);
}

void configureLoRa() {
  setLoRaChannel(LORA_DEFAULT_CHANNEL);
  delay(50);
  forwardLoRaAT("AT+SF" + String(LORA_SPREAD_FACTOR));
  delay(50);
  forwardLoRaAT("AT+POWE" + String(LORA_TX_POWER_DBM));
  delay(50);
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

  // Allow USB command "CHx" to change channel at runtime.
  if (command.startsWith("CH")) {
    int ch = command.substring(2).toInt();
    setLoRaChannel(ch);
    return;  // Do NOT forward CHx to remote scoreboards
  }

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

  // -------------------------------------------------------------------------
  // SET CHANNEL / SF / POWER AT STARTUP (factory defaults, same as remote)
  // -------------------------------------------------------------------------
  configureLoRa();
}

void loop() {
  if (!Serial.available()) {
    return;
  }
  processUsbCommand(Serial.readStringUntil('\n'));
}
