# NOVIS node firmware (ESP32)

Skeleton firmware for the sensor node. It samples the thermal array, the
ultrasonic rangers, and the acoustic echoes, builds a framed and encrypted
stream, and sends it over Bluetooth Low Energy to the host.

> **Board note:** the node MCU was switched from an nRF52840 ProMicro clone to
> a plain **ESP32-WROOM-32 DevKit** on 1 Sept 2026 — its UF2 bootloader and
> unreliable native-USB serial cost more debugging time than any sensor did.
> See `docs/hardware_log.md` section 3 for the full reasoning. This file, and
> `novis_node/`, describe the ESP32 as the current target.

This is a skeleton: the framing, fragmentation, and crypto structure are in
place. Per-sensor drivers have been prototyped and compile-verified on ESP32
in `bench_tests/` (see below) but not yet folded into `novis_node/sensors.cpp`
itself, and the BLE side still needs a real port — see "Status" below.

## Toolchain

- Arduino IDE (or arduino-cli) with the **esp32** board package (by Espressif
  Systems). Board index URL:
  `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
- Select **ESP32 Dev Module** under Tools > Board.
- ESP32's BLE stack (`BLEDevice.h`, bundled with the board package, or the
  third-party `NimBLE-Arduino` library) is a **different API** from Bluefruit
  — nothing here is a drop-in nRF52-to-ESP32 swap for the BLE side.

Libraries used by the drivers in `bench_tests/` (install via Library Manager):

| Need | Library | Status on ESP32 |
|---|---|---|
| MLX90640 thermal (I2C) | `Adafruit MLX90640` | compile + hardware verified, see `bench_tests/B2_thermal` |
| HC-SR04 ultrasonic | manual trigger/echo timing (no library) | hardware verified, see `bench_tests/B3_sonar` |
| INMP441 microphone | ESP32's own `driver/i2s.h` (not the nRF52 I2S registers) | hardware verified, see `bench_tests/B4_microphone` |
| ChaCha20-Poly1305 | `rweather/Crypto` (ChaChaPoly) | compiles and runs, see `bench_tests/crypto_compile_check` |

## Wiring (summary — see docs/hardware_log.md section 6-8 for the full story)

| Peripheral | ESP32 pins | Notes |
|---|---|---|
| MLX90640 | GPIO21 (SDA), GPIO22 (SCL) | address 0x33; our module is a GY-MCU90640 — its `PS` pin **must** go to GND, see hardware_log.md section 4; 4.7k pull-ups required on SDA/SCL |
| HC-SR04 x2 | TRIG: GPIO16/18, ECHO: GPIO17/19 | ECHO through a 1k/2k divider to 3.3V — never straight into a GPIO |
| INMP441 | SCK: GPIO14, WS: GPIO15, SD: GPIO32 | `L/R` to GND, or it outputs nothing |
| Speaker (via PAM8302) | GPIO4 | PAM8302's `SD` pin must be tied to VIN on our board, or the amp stays muted |
| LiPo | battery pad | through the board regulator |

## Bench test sketches (`bench_tests/`)

Each subfolder is a standalone, individually-flashable sketch that tests one
piece before it's combined — same "one component, test, then the next" rule
the build guide uses throughout Part B. **Compile-verified for
`esp32:esp32:esp32`**, and the B2-B5 sensor tests have all passed on real
hardware. See `docs/hardware_log.md` for the debugging history behind each.

| Folder | What it tests | Hardware status |
|---|---|---|
| `i2c_scanner/` | any I2C bus — the first thing to run when something's wrong | utility, not a pass/fail test |
| `B2_thermal/` | MLX90640 thermal sensor | **PASS** |
| `B3_sonar/` | HC-SR04 x2 ultrasonic | **PASS** |
| `B4_microphone/` | INMP441 mic | **PASS** |
| `B5_speaker_chirp/` | PAM8302 + speaker, chirp only | **PASS** |
| `B5_mic_speaker_echo_test/` | speaker + mic together (the real echo test) | **PASS** |
| `sensors_combined_compile_check/` | all four drivers together, real B6 pins, in the shape `sensors.cpp` needs | compiles clean; not run as a combined unit on hardware yet |
| `B6_full_module_test/` | all four sensors together, on the real assembled module, printed to Serial — see `docs/NOVIS_Final_Module_Build.md` | **PASS** on the assembled module, USB power |
| `crypto_compile_check/` | ChaCha20-Poly1305 via the `Crypto` library | compiles and runs |

## Live dashboard + dataset capture (`dashboard/`)

`dashboard/dashboard.ino` grew out of the `B6_full_module_test` bring-up test
into a standing tool, so it lives outside `bench_tests/` rather than as one
more one-component check. The ESP32 serves its own WiFi AP (`NOVIS-B6`) and a
browser dashboard at `http://192.168.4.1/`: a live thermal heatmap, sonar and
echo graphs on a distance axis, and a label/capture/download flow for
building the paper's dataset straight from the browser — no laptop-side
tooling needed. **PASS** on the assembled module, both USB and battery power;
see `docs/hardware_log.md` section 8 for the two faults found getting it
there (a loose ground, and a WiFi/I2C startup-ordering bug worth remembering
for the BLE port below).

## Build and flash

Open `novis_node/novis_node.ino` in the Arduino IDE, select **ESP32 Dev
Module** and the serial port, then Upload (hold **BOOT** if it doesn't
auto-reset). The skeleton still advertises as `NOVIS-Node` and streams test
patterns — the BLE side has not been ported yet, see Status below.

## Files

| File | Role |
|---|---|
| `novis_node/novis_node.ino` | main sketch: sampling loop, sealing, BLE notify — **BLE side still targets Bluefruit (nRF52-only), not yet ported to ESP32** |
| `novis_node/protocol.h` | wire protocol (mirrors `host/protocol.py`) |
| `novis_node/sensors.h/.cpp` | sensor driver interface — stubs; a compile-verified ESP32 draft exists at `bench_tests/sensors_combined_compile_check/`, not yet moved in here |
| `novis_node/crypto.h` | AEAD interface — stub; `bench_tests/crypto_compile_check/` has a compile-verified ESP32 implementation, not yet moved in here |

## Status / before real use

1. Fold the driver bodies from `bench_tests/sensors_combined_compile_check/`
   into `sensors.cpp`. B2-B5 have all passed individually on hardware, so this
   is now unblocked.
2. Fold `bench_tests/crypto_compile_check/` into `crypto.cpp`.
3. **Port `novis_node.ino`'s BLE server from Bluefruit to an ESP32 BLE
   stack.** This is real, unstarted work, not a small tweak — Bluefruit does
   not exist on ESP32.
4. Replace the placeholder all-zero key: pair with LE Secure Connections (or
   the ESP32 BLE stack's equivalent) and run an HKDF handshake over the
   control characteristic, then call `crypto_set_session` with the derived
   key and salt. The host uses the same placeholder key in its skeleton, so
   the two interoperate on the bench only.
