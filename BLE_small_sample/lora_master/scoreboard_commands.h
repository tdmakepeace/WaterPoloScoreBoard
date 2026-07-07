#ifndef SCOREBOARD_COMMANDS_H
#define SCOREBOARD_COMMANDS_H

#include <Arduino.h>

const int buzzerPin = 10;

const int SEG_A = 8;
const int SEG_B = 7;
const int SEG_C = 6;
const int SEG_D = 5;
const int SEG_E = 4;
const int SEG_F = 3;
const int SEG_G = 2;
const int SEG_DP = 9;

const int SEG_1A = A6;
const int SEG_1B = A5;
const int SEG_1C = A4;
const int SEG_1D = A3;
const int SEG_1E = A2;
const int SEG_1F = A1;
const int SEG_1G = A0;
const int SEG_1DP = A7;

const uint8_t digits[10][7] = {
    {LOW, LOW, LOW, LOW, LOW, LOW, HIGH},
    {HIGH, LOW, LOW, HIGH, HIGH, HIGH, HIGH},
    {LOW, LOW, HIGH, LOW, LOW, HIGH, LOW},
    {LOW, LOW, LOW, LOW, HIGH, HIGH, LOW},
    {HIGH, LOW, LOW, HIGH, HIGH, LOW, LOW},
    {LOW, HIGH, LOW, LOW, HIGH, LOW, LOW},
    {LOW, HIGH, LOW, LOW, LOW, LOW, LOW},
    {LOW, LOW, LOW, HIGH, HIGH, HIGH, HIGH},
    {LOW, LOW, LOW, LOW, LOW, LOW, LOW},
    {LOW, LOW, LOW, LOW, HIGH, LOW, LOW},
};

const uint8_t digitstens[10][7] = {
    {HIGH, HIGH, HIGH, HIGH, HIGH, HIGH, HIGH},
    {HIGH, LOW, LOW, HIGH, HIGH, HIGH, HIGH},
    {LOW, LOW, HIGH, LOW, LOW, HIGH, LOW},
    {LOW, LOW, LOW, LOW, HIGH, HIGH, LOW},
    {HIGH, LOW, LOW, HIGH, HIGH, LOW, LOW},
    {LOW, HIGH, LOW, LOW, HIGH, LOW, LOW},
    {LOW, HIGH, LOW, LOW, LOW, LOW, LOW},
    {LOW, LOW, LOW, HIGH, HIGH, HIGH, HIGH},
    {LOW, LOW, LOW, LOW, LOW, LOW, LOW},
    {LOW, LOW, LOW, LOW, HIGH, LOW, LOW},
};

const int segPins[7] = {SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G};
const int segPinstens[7] = {SEG_1A, SEG_1B, SEG_1C, SEG_1D, SEG_1E, SEG_1F, SEG_1G};

inline void scoreboardSetupPins() {
  for (int i = 0; i < 7; i++) {
    pinMode(segPins[i], OUTPUT);
    digitalWrite(segPins[i], HIGH);
    pinMode(segPinstens[i], OUTPUT);
    digitalWrite(segPinstens[i], HIGH);
  }
  pinMode(SEG_DP, OUTPUT);
  pinMode(SEG_1DP, OUTPUT);
  digitalWrite(SEG_DP, HIGH);
  digitalWrite(SEG_1DP, HIGH);
  pinMode(buzzerPin, OUTPUT);
  digitalWrite(buzzerPin, LOW);
}

inline void showDigit(int n) {
  n = constrain(n, 0, 9);
  for (int i = 0; i < 7; i++) {
    digitalWrite(segPins[i], digits[n][i]);
  }
}

inline void showDigittens(int n) {
  n = constrain(n, 0, 9);
  for (int i = 0; i < 7; i++) {
    digitalWrite(segPinstens[i], digitstens[n][i]);
  }
}

inline void clearDisplay() {
  for (int i = 0; i < 7; i++) {
    digitalWrite(segPins[i], HIGH);
    digitalWrite(segPinstens[i], HIGH);
  }
  digitalWrite(SEG_DP, HIGH);
  digitalWrite(SEG_1DP, HIGH);
}

inline bool handleScoreboardCommand(const String& command, String* bleAckOut) {
  if (command == "TEST") {
    digitalWrite(SEG_DP, LOW);
    digitalWrite(buzzerPin, HIGH);
    delay(50);
    digitalWrite(buzzerPin, LOW);
    if (bleAckOut != nullptr) {
      *bleAckOut = "D10 TEST";
    }
    return true;
  }

  if (command == "BUZZER") {
    if (bleAckOut != nullptr) {
      *bleAckOut = "BUZZER";
    }
    digitalWrite(buzzerPin, HIGH);
    delay(500);
    digitalWrite(buzzerPin, LOW);
    delay(100);
    return true;
  }

  if (command == "CHANGE") {
    if (bleAckOut != nullptr) {
      *bleAckOut = "CHANGE";
    }
    digitalWrite(buzzerPin, HIGH);
    delay(1000);
    digitalWrite(buzzerPin, LOW);
    delay(100);
    clearDisplay();
    return true;
  }

  if (command == "END") {
    if (bleAckOut != nullptr) {
      *bleAckOut = "END";
    }
    digitalWrite(buzzerPin, HIGH);
    delay(1000);
    digitalWrite(buzzerPin, LOW);
    delay(100);
    clearDisplay();
    return true;
  }

  if (command == "exit") {
    if (bleAckOut != nullptr) {
      *bleAckOut = "exit";
    }
    clearDisplay();
    return true;
  }

  if (command == "0") {
    clearDisplay();
    return true;
  }

  if (command >= "1") {
    int n = command.toInt();
    int tens = n / 10;
    int ones = n % 10;
    showDigit(ones);
    showDigittens(tens);
    Serial.print(n);
    Serial.print(" tens :");
    Serial.print(tens);
    Serial.print(" ones :");
    Serial.println(ones);
    return true;
  }

  return false;
}

#endif
