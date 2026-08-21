#include "scoreboard_commands.h"

const unsigned long LORA_BAUD = 9600;

// ---------------------------------------------------------------------------
// LoRa CHANNEL CONFIGURATION (same table as master)
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
// SELECT WHICH CHANNEL THIS REMOTE SCOREBOARD SHOULD USE
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

// Pool link: ~30 m, over water, bodies in the path. Must match the master.
const uint8_t LORA_SPREAD_FACTOR = 7;   // SF5–12; 7 = fast, plenty for 30 m
const uint8_t LORA_TX_POWER_DBM  = 22;  // 0–22 dBm; 22 = max punch through bodies

// ---------------------------------------------------------------------------
// Send AT commands to LoRa module
// ---------------------------------------------------------------------------
void forwardLoRaAT(const String& cmd) {
  Serial1.println(cmd);
  Serial.print("LoRa AT: ");
  Serial.println(cmd);
}

// ---------------------------------------------------------------------------
// Set LoRa channel (frequency)
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
  scoreboardSetupPins();

  Serial.begin(9600);
  while (!Serial) {
  }

  Serial1.begin(LORA_BAUD);
  Serial1.setTimeout(50);

  Serial.println("LoRa remote scoreboard ready");

  // -------------------------------------------------------------------------
  // SET CHANNEL / SF / POWER AT STARTUP (factory defaults, same as master)
  // -------------------------------------------------------------------------
  configureLoRa();
}

// ---------------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------------
void loop() {
  if (!Serial1.available()) {
    return;
  }

  String command = Serial1.readStringUntil('\n');
  command.trim();
  if (command.length() == 0) {
    return;
  }

  Serial.print("LoRa RX: ");
  Serial.println(command);

  // Remote boards DO NOT change channel based on LoRa commands.
  // Only scoreboard commands are processed.
  handleScoreboardCommand(command, nullptr);
}
