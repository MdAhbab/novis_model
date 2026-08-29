# NOVIS Hardware Build Log

Running lab notebook for the physical node build (Part A–B of `NOVIS_Build_Guide.md`).
Each entry records what was actually done and measured, not the plan.

## 2026-08-29 — Part A (software) + Part B1 (board alive test)

### Toolchain installed
- Arduino IDE 2.3.10
- Arduino CLI 1.5.1
- Adafruit nRF52 board core v1.7.0

### Correction to the build guide
The guide's Adafruit board-manager URL is dead:

```
https://www.adafruit.com/package_adafruit_index.json   # 404s now
```

Working URL used instead:

```
https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
```

### Libraries installed
- `Adafruit MLX90640` 1.1.2
- `Adafruit BusIO` 1.17.4
- `Crypto` (Rhys Weatherley) 0.4.0

(Installing `Adafruit MLX90640` pulls in a large set of unrelated Adafruit
library dependencies automatically — expected, harmless, just extra disk
space.)

### Board identification
- Board is a Nice!Nano-compatible nRF52840 Pro Micro clone.
- No dedicated "Nice!Nano" entry in Adafruit's board index, so per the guide's
  fallback we selected: **Adafruit Feather nRF52840 Express**
  (FQBN `adafruit:nrf52:feather52840`).
- Enumerates as a native USB serial port: **COM6** (on this Windows machine).
  A second port, COM3, is an unrelated existing serial device on the PC — not
  the node.

### B1 — Board alive test

Before any upload, the board blinks its LED **red/blue alternating** — this is
the factory nRF52 bootloader (DFU) animation, not application code. Do not
mistake this for a passing Blink test.

Test sketch used (`Blink.ino`):

```cpp
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(1000);
  digitalWrite(LED_BUILTIN, LOW);
  delay(1000);
}
```

Compiled and flashed via `arduino-cli`:

```bash
arduino-cli compile --fqbn adafruit:nrf52:feather52840 Blink
arduino-cli upload -p COM6 --fqbn adafruit:nrf52:feather52840 Blink
```

Result: `Device programmed` — upload succeeded. Sketch size 21244 bytes (2%
of 815104), 3096 bytes global RAM (1%).

**Status: PASS.**

### Next step
Part B2 — MLX90640 thermal sensor wiring and test.
