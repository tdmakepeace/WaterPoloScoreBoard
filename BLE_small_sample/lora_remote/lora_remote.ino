#include "scoreboard_commands.h"

const unsigned long LORA_BAUD = 9600;

void setup() {
  scoreboardSetupPins();

  Serial.begin(9600);
  while (!Serial) {
  }

  Serial1.begin(LORA_BAUD);
  Serial1.setTimeout(50);

  Serial.println("LoRa remote scoreboard ready");
}

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
  handleScoreboardCommand(command, nullptr);
}
