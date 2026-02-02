#include <ArduinoBLE.h>

BLEService gpioService("6E400001-B5A3-F393-E0A9-E50E24DCCA9E");
BLECharacteristic rxChar("6E400002-B5A3-F393-E0A9-E50E24DCCA9E", BLEWrite, 20);
BLECharacteristic txChar("6E400003-B5A3-F393-E0A9-E50E24DCCA9E", BLENotify, 20);

// Common Anode 7-segment display demo (1 digit)
// Segments: a b c d e f g (optional dp)
// Wiring below assumes segments on pins 8–2 and dp on 9; adjust as needed.
const int buzzerPin = 10;


// Segment pin mapping (Arduino digital pins)
const int SEG_A = 8;
const int SEG_B = 7;
const int SEG_C = 6;
const int SEG_D = 5;
const int SEG_E = 4;
const int SEG_F = 3;
const int SEG_G = 2;
const int SEG_DP = 9; // optional

const int SEG_1A = A6;
const int SEG_1B = A5;
const int SEG_1C = A4;
const int SEG_1D = A3;
const int SEG_1E = A2;
const int SEG_1F = A1;
const int SEG_1G = A0;
const int SEG_1DP = A7; // optional

// Common anode control: LOW turns segment ON, HIGH turns segment OFF
// Digit patterns: a b c d e f g (dp ignored here)
//                   a b c d e f g
const uint8_t digits[10][7] = {
  // 0
  {LOW, LOW, LOW, LOW, LOW, LOW, HIGH},
  // 1
  {HIGH, LOW, LOW, HIGH, HIGH, HIGH, HIGH},
  // 2
  {LOW, LOW, HIGH, LOW, LOW, HIGH, LOW},
  // 3
  {LOW, LOW, LOW, LOW, HIGH, HIGH, LOW},
  // 4
  {HIGH, LOW, LOW, HIGH, HIGH, LOW, LOW},
  // 5
  {LOW, HIGH, LOW, LOW, HIGH, LOW, LOW},
  // 6
  {LOW, HIGH, LOW, LOW, LOW, LOW, LOW},
  // 7
  {LOW, LOW, LOW, HIGH, HIGH, HIGH, HIGH},
  // 8
  {LOW, LOW, LOW, LOW, LOW, LOW, LOW},
  // 9
  {LOW, LOW, LOW, LOW, HIGH, LOW, LOW}
};

const uint8_t digitstens[10][7] = {
  // 0
  {HIGH, HIGH, HIGH, HIGH, HIGH, HIGH, HIGH},
  // 1
  {HIGH, LOW, LOW, HIGH, HIGH, HIGH, HIGH},
  // 2
  {LOW, LOW, HIGH, LOW, LOW, HIGH, LOW},
  // 3
  {LOW, LOW, LOW, LOW, HIGH, HIGH, LOW},
  // 4
  {HIGH, LOW, LOW, HIGH, HIGH, LOW, LOW},
  // 5
  {LOW, HIGH, LOW, LOW, HIGH, LOW, LOW},
  // 6
  {LOW, HIGH, LOW, LOW, LOW, LOW, LOW},
  // 7
  {LOW, LOW, LOW, HIGH, HIGH, HIGH, HIGH},
  // 8
  {LOW, LOW, LOW, LOW, LOW, LOW, LOW},
  // 9
  {LOW, LOW, LOW, LOW, HIGH, LOW, LOW}
};


const int segPins[7] = {SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G};
const int segPinstens[7] = {SEG_1A, SEG_1B, SEG_1C, SEG_1D, SEG_1E, SEG_1F, SEG_1G};

void setup() {
  // Segment pins as outputs
  for (int i = 0; i < 7; i++) {
    pinMode(segPins[i], OUTPUT);
    digitalWrite(segPins[i], HIGH);
  }
  for (int i = 0; i < 7; i++) {
    pinMode(segPinstens[i], OUTPUT);
    digitalWrite(segPinstens[i], HIGH);
  }
  pinMode(SEG_DP, OUTPUT);
  pinMode(SEG_1DP, OUTPUT);
  // Turn off decimal point by default
  digitalWrite(SEG_DP, HIGH); // common anode: HIGH = OFF
  digitalWrite(SEG_1DP, HIGH); // common anode: HIGH = OFF
  digitalWrite(buzzerPin,LOW);

  Serial.begin(9600);
  if (Serial) {
    while (!Serial);
  }
  
  if (!BLE.begin()) {
    Serial.println("BLE failed to start");
    while (1);
  }

  BLE.setLocalName("WaterPolo_2");
  BLE.setAdvertisedService(gpioService);
  gpioService.addCharacteristic(rxChar);
  gpioService.addCharacteristic(txChar);
  BLE.addService(gpioService);

  BLE.advertise();
  Serial.println("BLE GPIO service started");

}

void showDigit(int n) {
  n = constrain(n, 0, 9);
  for (int i = 0; i < 7; i++) {
    digitalWrite(segPins[i], digits[n][i]);
  }
}

void showDigittens(int n) {
  n = constrain(n, 0, 9);
  for (int i = 0; i < 7; i++) {
    digitalWrite(segPinstens[i], digitstens[n][i]);
  }
}

void clearDisplay() {
  for (int i = 0; i < 7; i++) {
    digitalWrite(segPins[i], HIGH); // OFF for common anode
    digitalWrite(segPinstens[i], HIGH); // OFF for common anode
  }
  digitalWrite(SEG_DP, HIGH);
  digitalWrite(SEG_1DP, HIGH);
}

void loop() {
  BLEDevice central = BLE.central();

  if (central) {
    Serial.print("Connected to: ");
    Serial.println(central.address());
    clearDisplay();

    while (central.connected()) {
      digitalWrite(SEG_DP, HIGH);
      if (rxChar.written()) {
        String command = String((char*)rxChar.value());
        command.trim();
        command = command.substring(0, 10); // Optional: limit to 10 chars
        Serial.print("Command: ");
        Serial.println(command);

        if (command == "TEST") {
          digitalWrite(SEG_DP, LOW);
          digitalWrite(buzzerPin, HIGH);
          delay (50);
          digitalWrite(buzzerPin, LOW);
          txChar.writeValue("D10 TEST");
        } else if (command == "BUZZER") {
          txChar.writeValue("BUZZER");
          for (int i =0; i<1 ; i++){
            digitalWrite(buzzerPin, HIGH); // Send 1KHz sound signal...
            delay (500);
            digitalWrite(buzzerPin, LOW);     // Stop sound...
            delay (100); 
          }
        } else if (command == "CHANGE") {
          txChar.writeValue("CHANGE");
          for (int i =0; i<1 ; i++){
            digitalWrite(buzzerPin, HIGH); // Send 1KHz sound signal...
            delay (1000);
            digitalWrite(buzzerPin, LOW);     // Stop sound...
            delay (100); 
            clearDisplay();

          } 
        } else if (command == "END") {
          txChar.writeValue("END");
          for (int i =0; i<1 ; i++){
            digitalWrite(buzzerPin, HIGH); // Send 1KHz sound signal...
            delay (1000);
            digitalWrite(buzzerPin, LOW);     // Stop sound...
            delay (100); 
            clearDisplay();

          }          
        } else if (command == "exit") {
          txChar.writeValue("exit");
          clearDisplay();
        } else if (command >= "1") {
          int n = command.toInt();
          int tens = n / 10;
          int ones = n % 10;
          showDigit(ones);
          showDigittens(tens);
          Serial.print(n);
          Serial.print("tens :"); 
          Serial.print(tens);
          Serial.print(" ones :");
          Serial.println(ones);
        }
         else if (command == "0") {
          clearDisplay();
        }
      }
    }

    Serial.println("Disconnected");
  }
}