// Sensor driver interface for the NOVIS node.
//
// These are stubs with the exact output formats the protocol expects. Fill the
// bodies in sensors.cpp with the real library calls:
//   - MLX90640: Adafruit_MLX90640 or the Melexis driver (I2C).
//   - HC-SR04 : NewPing, or a manual trigger/echo pulse-width read.
//   - INMP441 : the nRF52 I2S peripheral (PDM/I2S).
//   - chirp   : a PWM/timer square or swept tone on the speaker pin.
#ifndef NOVIS_SENSORS_H
#define NOVIS_SENSORS_H

#include <stdint.h>
#include "protocol.h"

// Fill thermal[768] with int16 pixels, row-major, 32 wide by 24 tall.
// Suggested encoding: temperature in centi-degrees Celsius (25.0 C -> 2500).
// Returns true on a fresh frame, false if the sensor was not ready.
bool sensors_read_thermal(int16_t thermal[NOVIS_THERMAL_PIXELS]);

// Emit a chirp, then fill echo[960] with int16 PCM at 16 kHz (60 ms window).
bool sensors_capture_echo(int16_t echo[NOVIS_ECHO_SAMPLES]);

// Fill two ranges in millimeters (0 = no echo). status bit0/bit1 = valid flags.
bool sensors_read_sonar(uint16_t *range_mm_left, uint16_t *range_mm_right,
                        uint8_t *status);

// One-time hardware init (I2C, I2S, GPIO). Returns false on any failure.
bool sensors_begin(void);

#endif  // NOVIS_SENSORS_H
