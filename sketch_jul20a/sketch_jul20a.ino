#include <ArduinoBLE.h>

BLEService gpioService("6E400001-B5A3-F393-E0A9-E50E24DCCA9E");
BLECharacteristic rxChar("6E400002-B5A3-F393-E0A9-E50E24DCCA9E", BLEWrite, 20);
BLECharacteristic txChar("6E400003-B5A3-F393-E0A9-E50E24DCCA9E", BLENotify, 20);

const int ledPin = 9;

void setup() {
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);

  Serial.begin(9600);
  if (Serial) {
    while (!Serial);
  }


  if (!BLE.begin()) {
    Serial.println("BLE failed to start");
    while (1);
  }

  BLE.setLocalName("Nano33BLE");
  BLE.setAdvertisedService(gpioService);
  gpioService.addCharacteristic(rxChar);
  gpioService.addCharacteristic(txChar);
  BLE.addService(gpioService);

  BLE.advertise();
  Serial.println("BLE GPIO service started");
}

void loop() {
  BLEDevice central = BLE.central();

  if (central) {
    Serial.print("Connected to: ");
    Serial.println(central.address());

    while (central.connected()) {
      if (rxChar.written()) {
        String command = String((char*)rxChar.value());
        command.trim();
        command = command.substring(0, 10); // Optional: limit to 10 chars
        Serial.print("Command: ");
        Serial.println(command);

        if (command == "TEST") {
          digitalWrite(ledPin, HIGH);
          delay (100);
          digitalWrite(ledPin, LOW);
          txChar.writeValue("D9 TEST");
        } else if (command == "BUZZER") {
          txChar.writeValue("BUZZER");
          for (int i =0; i<1 ; i++){
            digitalWrite(ledPin, HIGH); // Send 1KHz sound signal...
            delay (2000);
            digitalWrite(ledPin, LOW);     // Stop sound...
            delay (100); 
          }
          
        } else if (command == "CHANGE") {
          txChar.writeValue("Change");
          for (int i =0; i<3 ; i++){
            digitalWrite(ledPin, HIGH); // Send 1KHz sound signal...
            delay (100);
            digitalWrite(ledPin, LOW);     // Stop sound...
            delay (100); 
          }
          
        } else if (command == "END") {
          txChar.writeValue("End");
          for (int i =0; i<2 ; i++){
            digitalWrite(ledPin, HIGH); // Send 1KHz sound signal...
            delay (1000);
            digitalWrite(ledPin, LOW);     // Stop sound...
            delay (100); 
          }
          
        } else {
          txChar.writeValue("Unknown command");
        }
      }
    }

    Serial.println("Disconnected");
  }
}
