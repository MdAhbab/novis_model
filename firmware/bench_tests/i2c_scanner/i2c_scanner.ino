/*
  NOVIS bench test - I2C scanner (ESP32)

  Run this whenever anything I2C-related looks wrong. It is the fastest way
  to tell "wiring/power problem" apart from "code problem".

  Wiring: whatever I2C device you're checking, SDA -> GPIO21, SCL -> GPIO22
  (ESP32 defaults - matches the MLX90640 wiring used throughout this project).

  Read the result like this:
    - only 0x33 (the MLX90640's address), repeatedly -> bus is healthy
    - phantom extra addresses appearing/disappearing -> floating bus (missing
      pull-ups) or a device still holding the bus from an aborted transfer
    - nothing at all -> check power, GND, and that SDA/SCL aren't swapped

  See docs/hardware_log.md section 5a and section 4 (the MLX90640 GY-MCU90640
  investigation) for the full story of how this was used.
*/

#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(2000);
  Wire.begin(21, 22);        // ESP32. On nRF52: Wire.setPins(31, 29); Wire.begin();
  Serial.println("I2C Scanner starting...");
}

void loop() {
  int found = 0;
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print("Found device at address 0x");
      if (addr < 16) Serial.print("0");
      Serial.println(addr, HEX);
      found++;
    }
  }
  if (found == 0) Serial.println("No I2C devices found.");
  Serial.println("-----");
  delay(2000);
}
