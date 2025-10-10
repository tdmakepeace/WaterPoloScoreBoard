#include <ArduinoBLE.h>

BLEService gpioService("6E400001-B5A3-F393-E0A9-E50E24DCCA9E");
BLECharacteristic rxChar("6E400002-B5A3-F393-E0A9-E50E24DCCA9E", BLEWrite, 20);
BLECharacteristic txChar("6E400003-B5A3-F393-E0A9-E50E24DCCA9E", BLENotify, 20);

const int buzzerPin = 9;
const int lightPin = 10;


void setup() {
  pinMode(2, OUTPUT);  // Digital pin
  pinMode(3, OUTPUT);  // Digital pin
  pinMode(4, OUTPUT);  // Digital pin
  pinMode(5, OUTPUT);  // Digital pin
  pinMode(6, OUTPUT);  // Digital pin
  pinMode(7, OUTPUT);  // Digital pin
  pinMode(8, OUTPUT);  // Digital pin
  pinMode(A0, OUTPUT); // Set analog pin A0 as digital output
  pinMode(A1, OUTPUT); // Set analog pin A0 as digital output
  pinMode(A2, OUTPUT); // Set analog pin A0 as digital output
  pinMode(A3, OUTPUT); // Set analog pin A0 as digital output
  pinMode(A4, OUTPUT); // Set analog pin A0 as digital output
  pinMode(A5, OUTPUT); // Set analog pin A0 as digital output
  pinMode(A6, OUTPUT); // Set analog pin A0 as digital output

  pinMode(buzzerPin, OUTPUT);
  pinMode(lightPin, OUTPUT);
  digitalWrite(buzzerPin, LOW);
  digitalWrite(lightPin, LOW);
  digitalWrite(2, LOW);
  digitalWrite(3, LOW);
  digitalWrite(4, LOW);
  digitalWrite(5, LOW);
  digitalWrite(6, LOW);
  digitalWrite(7, LOW);
  digitalWrite(8, LOW);
  digitalWrite(9, LOW);
  digitalWrite(A0, LOW);
  digitalWrite(A1, LOW);
  digitalWrite(A2, LOW);
  digitalWrite(A3, LOW);
  digitalWrite(A4, LOW);
  digitalWrite(A5, LOW);
  digitalWrite(A6, LOW); 

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
          digitalWrite(buzzerPin, HIGH);
          digitalWrite(lightPin, HIGH);
          delay (50);
          digitalWrite(buzzerPin, LOW);
          txChar.writeValue("D9 TEST");
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
            delay (1500);
            digitalWrite(buzzerPin, LOW);     // Stop sound...
            delay (100); 
          }
        } else if (command == "END") {
          txChar.writeValue("END");
          for (int i =0; i<2 ; i++){
            digitalWrite(buzzerPin, HIGH); // Send 1KHz sound signal...
            delay (500);
            digitalWrite(buzzerPin, LOW);     // Stop sound...
            delay (100); 
          }
          digitalWrite(buzzerPin, HIGH); // Send 1KHz sound signal...
          delay (1000);
          digitalWrite(buzzerPin, LOW);     // Stop sound...
          delay (100); 
        } else if (command == "0") {
          digitalWrite(2, LOW);
          digitalWrite(3, LOW);
          digitalWrite(4, LOW);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, LOW);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 

        } else if (command == "1") {
          digitalWrite(2, LOW);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, LOW);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 

        } else if (command == "2") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, LOW);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, LOW);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 

        } else if (command == "3") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else if (command == "4") {
          digitalWrite(2, LOW);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else if (command == "5") {
          digitalWrite(2, HIGH);
          digitalWrite(3, LOW);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, LOW);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
          } else if (command == "6") {
          digitalWrite(2, HIGH);
          digitalWrite(3, LOW);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else if (command == "7") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, LOW);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        }  else if (command == "8") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        }  else if (command == "9") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else if (command == "10") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, HIGH);
          digitalWrite(8, LOW);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else if (command == "11") {
          digitalWrite(2, LOW);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, LOW);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 

        } else if (command == "12") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, LOW);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, LOW);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 

        } else if (command == "13") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else if (command == "14") {
          digitalWrite(2, LOW);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else if (command == "15") {
          digitalWrite(2, HIGH);
          digitalWrite(3, LOW);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, LOW);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
          } else if (command == "16") {
          digitalWrite(2, HIGH);
          digitalWrite(3, LOW);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else if (command == "17") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, LOW);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        }  else if (command == "18") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        }  else if (command == "19") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, LOW);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else     if (command == "20") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, HIGH);
          digitalWrite(8, LOW);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 

        } else if (command == "21") {
          digitalWrite(2, LOW);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, LOW);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 

        } else if (command == "22") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, LOW);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, LOW);
          digitalWrite(8, HIGH);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 

        } else if (command == "23") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, HIGH);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 

        } else if (command == "24") {
          digitalWrite(2, LOW);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 
        } else if (command == "25") {
          digitalWrite(2, HIGH);
          digitalWrite(3, LOW);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, LOW);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 

          } else if (command == "26") {
          digitalWrite(2, HIGH);
          digitalWrite(3, LOW);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 
        } else if (command == "27") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, LOW);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 
        }  else if (command == "28") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 
        }  else if (command == "29") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, HIGH);
          digitalWrite(8, HIGH);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, LOW);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, HIGH);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 

        } else  if (command == "30") {
          digitalWrite(2, HIGH);
          digitalWrite(3, HIGH);
          digitalWrite(4, HIGH);
          digitalWrite(5, HIGH);
          digitalWrite(6, HIGH);
          digitalWrite(7, HIGH);
          digitalWrite(8, LOW);
          digitalWrite(A0, HIGH);
          digitalWrite(A1, HIGH);
          digitalWrite(A2, HIGH);
          digitalWrite(A3, HIGH);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, HIGH); 
        } else if (command == "OFF") {
          digitalWrite(2, LOW);
          digitalWrite(3, LOW);
          digitalWrite(4, LOW);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, LOW);
          digitalWrite(9, LOW);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW); 
        } else if (command == "exit") {
          digitalWrite(lightPin, LOW);
          digitalWrite(2, LOW);
          digitalWrite(3, LOW);
          digitalWrite(4, LOW);
          digitalWrite(5, LOW);
          digitalWrite(6, LOW);
          digitalWrite(7, LOW);
          digitalWrite(8, LOW);
          digitalWrite(9, LOW);
          digitalWrite(A0, LOW);
          digitalWrite(A1, LOW);
          digitalWrite(A2, LOW);
          digitalWrite(A3, LOW);
          digitalWrite(A4, LOW);
          digitalWrite(A5, LOW);
          digitalWrite(A6, LOW);  
        } else {
          txChar.writeValue("Unknown command");
        }
      }
    }

    Serial.println("Disconnected");
  }
}
