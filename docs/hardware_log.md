# NOVIS Hardware — Build Log & Handoff

**Branch:** `Hardware` · **Covers:** Part B of `docs/NOVIS_Build_Guide.md` · **Updated:** 30 Aug 2026

Read this before touching the hardware. It says what we are building, how far we
got, what is broken, and what has already been tried so nobody repeats it.

---

## 1. What we are building, and why this way

NOVIS makes a picture of a room **without a camera**.

```
MLX90640 thermal + 2x HC-SR04 sonar + INMP441 mic/speaker echo
        |
    nRF52840 node   <- only senses, packs, encrypts. No AI here.
        |
    BLE (ChaCha20-Poly1305 encrypted)
        |
    Host PC -> NOVISNet (~27M params)
        |
    grayscale + depth + inferred colour + colour confidence
```

The node is deliberately dumb. It runs on a small LiPo, and running a neural net
there would kill the battery in minutes. So the node only senses and transmits,
and the host does the heavy work. This split is one of the paper's contributions.

**Our job is Parts B–F**: build the node, write its drivers, receive data on the
host, capture real scenes, and measure power/range/latency. No GPU needed for any
of it — training is a separate track.

**The one rule:** one component → test → PASS → next component. Never wire several
sensors then debug. Section 4 is a long debugging story about *one* sensor; with
five wired at once it would have been hopeless.

---

## 2. Where we are

| Part | What | Status |
|---|---|---|
| A | Toolchain, libraries | **done** |
| B1 | nRF52840 alive (Blink) | **PASS** |
| B2 | MLX90640 thermal | **BLOCKED** — section 4 |
| B3 | HC-SR04 x2 | not started |
| B4 | INMP441 mic | not started |
| B5 | PAM8302 + speaker | not started |
| B6 | Full assembly | not started |
| C | `sensors.cpp`, `crypto.cpp` | not started |
| D | Host BLE receive | not started |
| E | 12-scene capture | **start ethics paperwork now** — takes weeks |
| F | Power/range/latency | not started |

Everything downstream is waiting on B2.

### Toolchain

Arduino IDE 2.3.10 + Arduino CLI 1.5.1. Cores: `adafruit:nrf52` 1.7.0,
`esp32:esp32` 3.3.11. Libraries: Adafruit MLX90640 1.1.2, Adafruit BusIO 1.17.4,
Crypto (Rhys Weatherley) 0.4.0.

**The build guide's board URL is dead.** Part A3 says to use
`https://www.adafruit.com/package_adafruit_index.json` — it 404s. Use instead:

```
https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

---

## 3. The two boards, and why we used both

We started on the **nRF52840** (the real target). When the thermal sensor would not
work, we moved it to an **ESP32** to answer one question: *does the problem follow
the sensor, or the board?* It followed the sensor — same failure on both. That is
why the ESP32 is in this document at all. It stays as a debugging tool; the final
node is nRF52840, because the firmware, BLE stack and power budget all assume it.

### 3a. nRF52840 ProMicro (target board)

A Nice!Nano-compatible clone, silkscreen `V1940`. **It has no `SDA`/`SCL` labels** —
pads are marked with raw port numbers (`O31`, `O29`, `1.15`, …). Two consequences:

**Select board "Nordic nRF52840 DK"** (`adafruit:nrf52:pca10056`), *not* Feather
nRF52840 Express. Reason: we opened the installed core's
`variants/pca10056/variant.cpp` and its pin map is the identity map — so Arduino
pin number equals the P0.xx number printed on the board (P1.xx = +32). With the
Feather variant the numbers do not line up and you drive the wrong pins.

| MLX90640 | Board pad | Arduino pin |
|---|---|---|
| SDA | `O31` | 31 |
| SCL | `O29` | 29 |
| VIN | `VCC` | — |
| GND | `GND` | — |

I2C pins must be set in code — the variant defaults (26/27) are wrong here:

```cpp
Wire.setPins(31, 29);   // SDA = P0.31, SCL = P0.29
Wire.begin();
```

**Warning — `VCC` measures 3.7 V** on USB power. The MLX90640's absolute maximum is
3.6 V. Do not power the sensor from this pin. (The `VDD` pad on the small 4-pin
debug header reads ~0.05 V — it is not a rail, ignore it.)

**Uploading is fiddly.** It uses a UF2 bootloader. App mode = one COM port (COM7
here); bootloader mode = a different one (COM6) plus a USB drive named `NICENANO`.
Auto touch-reset often fails with `No data received on serial port` or
`Timed out waiting for acknowledgement`. There is **no reset button** — to force
bootloader mode, short the `RST` pad to `GND` **twice quickly** (under half a
second apart) with a jumper wire, then press Upload immediately. Windows pops an
AutoPlay "file transfer" prompt for the drive — ignore it, Upload does not need it.

**LEDs:** blue is `LED_BUILTIN`, the one sketches control. Red is a hardware/charge
indicator and means nothing about firmware. Red+blue alternating at power-on is the
factory bootloader animation, not your sketch running.

### 3b. ESP32 DevKit (debug only)

ESP-WROOM-32 with CP2102. Far easier: labelled `3V3`, labelled GPIOs, and real
`EN` (reset) and `BOOT` buttons.

| MLX90640 | ESP32 pin |
|---|---|
| SDA | `D21` (GPIO21) |
| SCL | `D22` (GPIO22) |
| VIN | `3V3` |
| GND | `GND` |

Board: **ESP32 Dev Module** (`esp32:esp32:esp32`), COM8 here.

- **CP2102 driver:** Windows first showed the device as **Status: Error** with no
  COM port. Fixed by installing Silicon Labs' VCP driver (`CP210x_Windows_Drivers.zip`
  → `CP210xVCPInstaller_x64.exe`).
- **Upload:** hold **BOOT**, press Upload, release when "Connecting..." appears.
  Otherwise: `Wrong boot mode detected (0x13)! The chip needs to be in download mode.`
- **Serial Monitor:** open it *first*, then press **EN** to reset. Opening it after
  boot misses all the startup prints — this caused several false "nothing is
  printing" panics.

---

## 4. The blocker: MLX90640 thermal sensor

**Symptom:** `mlx.begin()` returns false ("MLX90640 not found") on both boards,
nearly always. Once on the nRF52 it printed `Outlier pixels: 5` and
`MLX90640 found!` — but then every `getFrame()` failed. **We have never read a
single thermal frame.**

Sensor is a generic **MLX90640BAA** 32x24 module (wide FOV).

### What is confirmed (measured, not assumed)

1. **The sensor is alive and correctly addressed.** An I2C scan finds a device at
   **0x33** — the MLX90640's default address — repeatedly, on both boards.
2. **It holds real data.** Reading its ID registers directly returns plausible
   unique values, so it is a genuine programmed part:
   ```
   0x2408 -> 0xCEB8
   0x2409 -> 0x018A
   0x2407 -> write ok (err=0) but no data came back
   ```
3. **Short reads work, long reads do not.** 2-byte register reads succeed.
   `mlx.begin()` — which dumps the **1664-byte** calibration EEPROM in 128-byte
   chunks — fails. This is our sharpest clue.
4. **The `SET I2C` solder jumper on the module is bridged** — confirmed by
   multimeter continuity (it beeps). Module is in I2C mode, not UART mode.
5. **Power at the sensor is fine** — 3.23 V measured at its own VIN/GND pins while
   running.

### What we already ruled out

Do not spend time on these again:

| Tried | Why we tried it | Result |
|---|---|---|
| Swapped MCU (nRF52840 → ESP32) | is it the board or the sensor? | same failure — it is the sensor side |
| I2C clock 100 kHz → 50 kHz | slower clock tolerates marginal wiring | no fix |
| Refresh rate 8 Hz → 2 Hz | give each frame read more time | no fix |
| Separate supply (LiPo → LM2596 → 3.3 V) | rule out a weak/noisy rail | no fix |
| Extra delay before `begin()` | let the bus/power settle after boot | no fix |
| Retry `begin()` 10 times | is it random or systematic? | 10/10 failed — systematic |
| Re-seating every wire | loose breadboard contact | behaviour changed, but no fix |
| **2x 4.7k pull-ups, SDA and SCL to 3V3** | scan showed floating-bus symptoms | **big improvement**, still no `begin()` |

### The pull-up finding — keep this

Before pull-ups, an I2C scan reported **phantom devices** (0x07, 0x08, 0x09, 0x10,
0x11, 0x12) alongside the real 0x33. Phantom low addresses mean the bus lines are
floating and the scanner is reading noise as an ACK.

Adding **4.7k from SDA to 3V3 and 4.7k from SCL to 3V3** cleaned the scan down to
just `0x33`. This generic breakout does not carry adequate pull-ups of its own, so
**these two resistors stay on the final node**, and this goes in the paper's
hardware section.

If phantom addresses come back later, the sensor is stuck holding the bus from an
aborted transfer. The probe sketch below starts with a bus-recovery routine
(toggle SCL 9 times with SDA released) that clears it.

### Two possible causes left

- **(a) A transfer-length limit.** Everything short works; only the long 128-byte
  chunked EEPROM read fails.
- **(b) Marginal physical connections.** Breadboard contacts or jumpers that
  survive short transactions but not sustained ones. Supported by behaviour
  changing when wires were re-seated, and by that one lone success.

Note: `Adafruit_MLX90640`'s `i2c_dev` member is **private**, so the 128-byte chunk
size cannot be reduced from a sketch. If (a) is confirmed, the fix means patching
the library or driving the Melexis API directly.

### Next step — run the read-size probe (section 5b)

Do this **before any more rewiring**. It settles (a) vs (b) with data instead of
another guess: it recovers a stuck bus, tests read sizes 2→250 bytes five times
each, then tries the full 1664-byte EEPROM in 32 / 64 / 128-byte chunks.

| Probe result | Meaning | Do this |
|---|---|---|
| All sizes fine, full EEPROM fails only at 128-byte chunks | (a) chunk limit | patch library to smaller chunks |
| Clean cutoff above some size (32 ok, 64 not) | (a) buffer limit | same, using the known good size |
| Small sizes fail randomly too | (b) electrical | stop debugging software — **solder** |

`endTransmission` error codes: `2` = address NACK, `3` = data NACK, `5` = timeout.

**If it is (b):** solder the four wires (VIN, GND, SCL, SDA) directly instead of
breadboarding, or move to a different breadboard with fresh jumpers. The guide
already wants the final assembly rigid (hot glue or perfboard) because sensors
shifting between recordings ruins dataset consistency — so doing this properly now
serves both purposes.

---

## 5. The code

### 5a. I2C scanner — the go-to sanity check

Run this whenever anything looks wrong. `0x33` and nothing else = bus healthy.
Phantom extra addresses = floating bus or a stuck sensor.

```cpp
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
```

### 5b. Read-size probe — run this next

Finds the exact read size where the bus breaks, which tells us cause (a) or (b).

```cpp
#include <Wire.h>

#define MLX_ADDR  0x33
#define SDA_PIN   21
#define SCL_PIN   22

// Clock out 9 bits with SDA released, in case the sensor is still holding the
// bus low from a transfer that was aborted mid-read.
void busRecover() {
  pinMode(SDA_PIN, INPUT_PULLUP);
  pinMode(SCL_PIN, OUTPUT);
  for (int i = 0; i < 9; i++) {
    digitalWrite(SCL_PIN, HIGH); delayMicroseconds(5);
    digitalWrite(SCL_PIN, LOW);  delayMicroseconds(5);
  }
  digitalWrite(SCL_PIN, HIGH);
  pinMode(SCL_PIN, INPUT_PULLUP);
  delay(10);
}

// Read `len` bytes starting at EEPROM word address `addr`.
// Returns how many bytes actually came back.
size_t tryRead(uint16_t addr, size_t len, byte *endTxErr) {
  Wire.beginTransmission(MLX_ADDR);
  Wire.write(addr >> 8);
  Wire.write(addr & 0xFF);
  *endTxErr = Wire.endTransmission(false);   // repeated start
  if (*endTxErr != 0) return 0;

  size_t recv = Wire.requestFrom((uint8_t)MLX_ADDR, len, true);
  while (Wire.available()) Wire.read();       // drain
  return recv;
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println();
  Serial.println("=== MLX90640 read-size probe ===");

  busRecover();

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setBufferSize(256);
  Wire.setTimeOut(1000);
  Wire.setClock(100000);
  delay(300);

  const size_t sizes[] = {2, 4, 8, 16, 32, 64, 128, 250};
  for (unsigned s = 0; s < sizeof(sizes) / sizeof(sizes[0]); s++) {
    size_t want = sizes[s];
    int ok = 0;
    byte lastErr = 0;
    for (int t = 0; t < 5; t++) {        // 5 tries, so one glitch isn't a "limit"
      byte err;
      if (tryRead(0x2400, want, &err) == want) ok++;
      else lastErr = err;
      delay(30);
    }
    Serial.print("read "); Serial.print(want);
    Serial.print(" bytes: "); Serial.print(ok); Serial.print("/5 ok");
    if (ok < 5) { Serial.print("   (last endTransmission err="); Serial.print(lastErr); Serial.print(")"); }
    Serial.println();
  }

  Serial.println();
  const size_t chunkSizes[] = {32, 64, 128};
  for (unsigned c = 0; c < sizeof(chunkSizes) / sizeof(chunkSizes[0]); c++) {
    size_t chunk = chunkSizes[c];
    uint16_t addr = 0x2400;
    size_t done = 0;
    bool failed = false;
    int failChunk = -1;
    for (int i = 0; done < 1664; i++) {
      size_t want = (1664 - done) > chunk ? chunk : (1664 - done);
      byte err;
      if (tryRead(addr, want, &err) != want) { failed = true; failChunk = i; break; }
      done += want;
      addr += want / 2;   // address is in 16-bit words
    }
    Serial.print("full 1664-byte EEPROM in "); Serial.print(chunk);
    Serial.print("-byte chunks: ");
    if (failed) {
      Serial.print("FAILED at chunk "); Serial.print(failChunk);
      Serial.print(" ("); Serial.print(done); Serial.println(" bytes read)");
    } else {
      Serial.println("OK - all 1664 bytes read");
    }
    delay(200);
  }

  Serial.println();
  Serial.println("=== done ===");
}

void loop() {}
```

### 5c. The actual B2 test — for once the bus is fixed

ESP32 version. On nRF52, replace `Wire.begin(21, 22);` with
`Wire.setPins(31, 29); Wire.begin();`.

```cpp
#include <Wire.h>
#include <Adafruit_MLX90640.h>

Adafruit_MLX90640 mlx;
float frame[32 * 24];

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("Starting MLX90640 test...");

  Wire.begin(21, 22);
  delay(1000);

  if (!mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire)) {
    Serial.println("ERROR: MLX90640 not found. Check your wiring.");
    while (1) delay(10);
  }
  Serial.println("MLX90640 found!");
  mlx.setMode(MLX90640_CHESS);
  mlx.setResolution(MLX90640_ADC_18BIT);
  mlx.setRefreshRate(MLX90640_8_HZ);
}

void loop() {
  int status = mlx.getFrame(frame);
  if (status == 0) {
    for (int y = 0; y < 24; y++) {
      for (int x = 0; x < 32; x++) {
        Serial.print(frame[y * 32 + x], 1);
        Serial.print(" ");
      }
      Serial.println();
    }
    Serial.println("-----");
  } else {
    Serial.print("getFrame failed, code: ");
    Serial.println(status);
  }
  delay(500);
}
```

**B2 passes only when** the grid shows room temperature (~20–30) **and** a hand in
front of the sensor makes those pixels jump to ~30–35. `MLX90640 found!` on its own
is not a pass — we learned that the hard way.

### 5d. Command line build/upload

Faster than the IDE and prints real errors.

```bash
# nRF52840 (double-tap RST-to-GND first if upload times out)
arduino-cli compile --fqbn adafruit:nrf52:pca10056 <sketch-dir>
arduino-cli upload -p COM7 --fqbn adafruit:nrf52:pca10056 <sketch-dir>

# ESP32 (hold BOOT during upload)
arduino-cli compile --fqbn esp32:esp32:esp32 <sketch-dir>
arduino-cli upload -p COM8 --fqbn esp32:esp32:esp32 <sketch-dir>

arduino-cli board list      # which port is which
```

---

## 6. After B2 — what comes next

### Remaining wiring (B3–B6)

- **HC-SR04 ECHO is 5 V and must go through the 1k/2k divider.** `5V x 2/(1+2) = 3.33V`.
  The junction *between* the two resistors goes to the MCU — not the end of a
  resistor. One divider per sensor. This is the one real way to destroy the board.
- **INMP441 `L/R` must be tied to GND** or the mic outputs nothing at all.
- **Speaker never connects directly to an MCU pin** — always through the PAM8302.
- Read the two sonars one after the other with a gap, or they hear each other's
  pings (cross-talk).
- Physical layout matters: mic ~3 cm from speaker, sonars ~20° left and right of
  centre, everything pointing the same way as the thermal array. Keep it rigid.
- On battery there is no 5 V rail, and many HC-SR04 units stop working below ~4.5 V.
  Test ours; if they fail, we need an RCWL-1601 or a boost converter — **and we must
  write down which we used.**

### Firmware (Part C)

The repo already has `novis_node.ino`, `protocol.h`, `sensors.h`, `crypto.h`.
Two files are ours:

- **`sensors.cpp`** — real drivers for all five sensors. The guide has a full
  reference implementation. Its eight `#define` pin numbers are examples and
  **must** be replaced with our real wiring — the guide calls this the number one
  cause of "it compiled but nothing works". Also note the guide's version calls
  `Wire.begin()` with no arguments; on our ProMicro clone that targets the wrong
  pins, so it needs `Wire.setPins(...)` first.
- **`crypto.cpp`** — ChaCha20-Poly1305 via the `Crypto` library. Nonce = 8-byte
  counter + 4-byte session salt.

**For the paper:** the firmware uses an **all-zero placeholder key** so node and
host talk on the bench. Fine for our experiments, and the paper already says so.
Do not describe it as secure.

### Numbers we still owe the paper

Write down what you actually measure, never what you expected:

- the filled-in B6 pin table
- current for all five cases in F1 (replaces the estimated 36.5 mA)
- real battery life (predicted 3.3 h — report the truth, even if it is 2 h)
- the F2 range table (1–10 m)
- HC-SR04 at 3.3 V: worked, or needed RCWL-1601 / boost converter?
- that the MLX90640 breakout needs external 4.7k pull-ups

### Part E — start the paperwork now

Ethics approval can take weeks and the 12-scene capture cannot legally start
without it. Needed: consent from everyone in the room, a simple consent form, and
face blurring before data leaves the recording machine. Split the dataset **by
scene, never by frame** — frames from the same room in both train and test will be
caught by reviewers. Worth stating in the paper: the 60 ms echo recordings are
stored as spectrograms and speech cannot be recovered from them — a genuine
privacy strength.
