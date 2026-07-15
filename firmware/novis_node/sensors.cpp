// Sensor driver stubs. Replace the TODO bodies with real library calls.
// The stubs return deterministic test patterns so the BLE and crypto path can
// be exercised on the bench before the sensors are wired.
#include "sensors.h"

#include <Arduino.h>

bool sensors_begin(void) {
  // TODO: Wire1.begin(); mlx.begin(0x33, &Wire1); configure I2S; set pin modes.
  return true;
}

bool sensors_read_thermal(int16_t thermal[NOVIS_THERMAL_PIXELS]) {
  // TODO: mlx.getFrame(float_buf); convert Celsius -> centi-Celsius int16.
  // Test pattern: a warm horizontal band so the host shows structure.
  for (int y = 0; y < 24; y++)
    for (int x = 0; x < 32; x++)
      thermal[y * 32 + x] = (int16_t)(2000 + (y > 10 && y < 16 ? 800 : 0));
  return true;
}

bool sensors_capture_echo(int16_t echo[NOVIS_ECHO_SAMPLES]) {
  // TODO: trigger the chirp, then read the I2S microphone for 60 ms.
  for (int i = 0; i < NOVIS_ECHO_SAMPLES; i++) echo[i] = 0;
  return true;
}

bool sensors_read_sonar(uint16_t *left, uint16_t *right, uint8_t *status) {
  // TODO: trigger each HC-SR04, time the echo pulse, convert to mm.
  *left = 1500;
  *right = 2200;
  *status = 0x03;  // both valid
  return true;
}
