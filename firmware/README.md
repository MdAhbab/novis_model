# NOVIS node firmware (nRF52840)

Skeleton firmware for the sensor node. It samples the thermal array, the
ultrasonic rangers, and the acoustic echoes, builds a framed and encrypted
stream, and sends it over Bluetooth Low Energy to the host.

This is a skeleton: the BLE, framing, fragmentation, and crypto structure are in
place, and the sensor driver bodies and the key handshake are marked with `TODO`
for you to complete on the real hardware.

## Toolchain

- Arduino IDE (or arduino-cli) with the **Adafruit nRF52** board package.
- Select your nRF52840 board (Feather nRF52840 Express, ProMicro nRF52840, or
  similar) under Tools > Board.
- The Bluefruit BLE library ships with that board package.

Add these libraries for the sensors and crypto (fill the stubs that use them):

| Need | Suggested library |
|---|---|
| MLX90640 thermal (I2C) | `Adafruit MLX90640` |
| HC-SR04 ultrasonic | `NewPing`, or manual trigger/echo timing |
| INMP441 microphone | nRF52 I2S/PDM peripheral |
| ChaCha20-Poly1305 | `rweather/Crypto` (ChaChaPoly), or CryptoCell / mbedTLS in the nRF Connect SDK |

## Wiring (summary)

| Peripheral | Bus | Notes |
|---|---|---|
| MLX90640 | I2C (SDA, SCL) | address 0x33 |
| HC-SR04 x2 | 2 GPIO each | trigger out, echo in; use a divider on echo to 3.3 V |
| INMP441 | I2S (BCLK, LRCLK, DIN) | left/right select to GND |
| Speaker | 1 PWM pin via transistor | chirp emitter |
| Li-Po | battery pad | 150 mAh, through the board regulator |

## Build and flash

Open `novis_node/novis_node.ino` in the Arduino IDE, select the board and the
serial port, then Upload. The skeleton advertises as `NOVIS-Node` and streams
test patterns until you fill the sensor stubs.

## Files

| File | Role |
|---|---|
| `novis_node/novis_node.ino` | main sketch: sampling loop, sealing, BLE notify |
| `novis_node/protocol.h` | wire protocol (mirrors `host/protocol.py`) |
| `novis_node/sensors.h/.cpp` | sensor driver interface and stubs |
| `novis_node/crypto.h` | AEAD interface (implement in crypto.cpp) |

## Before real use

1. Replace the sensor stubs in `sensors.cpp` with real driver calls.
2. Implement `crypto.cpp` with ChaCha20-Poly1305, ideally on CryptoCell.
3. Replace the placeholder all-zero key: pair with LE Secure Connections and run
   an HKDF handshake over the control characteristic, then call
   `crypto_set_session` with the derived key and salt. The host uses the same
   placeholder key in its skeleton, so the two interoperate on the bench only.
