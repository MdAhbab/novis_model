# NOVIS Hardware Build — Working Log & Handoff

**Branch:** `Hardware`
**Covers:** Part A (workstation setup) and Part B1–B2 of `docs/NOVIS_Build_Guide.md`
**Last updated:** 30 August 2026

This document is the running lab notebook for the physical sensor node. It records
what was actually done and actually measured — not the plan. Read it end to end
before touching the hardware; several things differ from the build guide, and the
differences are the important part.

---

## 1. What NOVIS is (one page)

NOVIS reconstructs a picture of a room **without a camera**.

```
MLX90640 thermal + 2x HC-SR04 sonar + INMP441 mic/speaker echo
        |
    nRF52840 node   <- senses, packs, encrypts. No AI on the node.
        |
    BLE (ChaCha20-Poly1305 AEAD)
        |
    Host PC -> NOVISNet (~27M param transformer)
        |
    grayscale + inverse-depth + inferred colour + colour-confidence
```

The node is deliberately "dumb": it only senses and transmits, and the host does
all the heavy work. That split is one of the paper's contributions, and it is why
the node runs on a small battery at all.

**Our track (hardware lead) is Parts B, C, D, E, F.** Model training is a separate
track and needs a GPU; nothing in Parts A–F does.

---

## 2. Where we are right now

| Part | What it is | Status |
|---|---|---|
| A | Workstation, Arduino toolchain, libraries | **DONE** |
| B1 | nRF52840 board alive (Blink) | **PASS** |
| B2 | MLX90640 thermal sensor | **BLOCKED** — see §7 |
| B3 | HC-SR04 x2 ultrasonic | not started |
| B4 | INMP441 microphone | not started |
| B5 | PAM8302 + speaker | not started |
| B6 | Full assembly | not started |
| C | `sensors.cpp` + `crypto.cpp` firmware | not started |
| D | Host BLE receive | not started |
| E | 12-scene capture | **start ethics paperwork now** — it takes weeks |
| F | Power / range / latency measurements | not started |

**The single blocker is B2.** Everything downstream waits on it. §7 documents it in
full so whoever picks this up does not repeat the same twelve experiments.

---

## 3. The rule we are following

From the build guide, and it has already paid for itself:

> One component -> test -> PASS -> next component.

Do not wire five sensors and then debug. Every hour lost in §7 would have been ten
hours if the sonar, mic and speaker had been on the board at the same time.

---

## 4. Workstation setup (Part A) — actual state

### Installed

| Component | Version | Location |
|---|---|---|
| Arduino IDE | 2.3.10 | `D:\demo\DIP\Arduino IDE` |
| Arduino CLI | 1.5.1 | `C:\Program Files\Arduino CLI\arduino-cli.exe` |
| Adafruit nRF52 core | 1.7.0 | `D:\ArduinoData\Arduino15` |
| ESP32 core | 3.3.11 | `D:\ArduinoData\Arduino15` |
| Arduino AVR core | 1.8.8 | `D:\ArduinoData\Arduino15` |

Libraries: `Adafruit MLX90640` 1.1.2, `Adafruit BusIO` 1.17.4, `Crypto`
(Rhys Weatherley) 0.4.0. Installing MLX90640 pulls in a large set of unrelated
Adafruit dependencies — expected, harmless, just disk space.

### Correction 1 — the build guide's board URL is dead

The guide (Part A3) says to use:

```
https://www.adafruit.com/package_adafruit_index.json      <-- 404s, do not use
```

The working URL is:

```
https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
```

For ESP32:

```
https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

### Correction 2 — everything was moved off C:

The C: drive had only 4.5 GB free and the ESP32 toolchain alone is ~1.5 GB
(it downloads both the Xtensa and RISC-V toolchains). Arduino data now lives on D:

```
data:      D:\ArduinoData\Arduino15
downloads: D:\ArduinoData\Arduino15\staging
user:      D:\ArduinoData\Sketchbook
```

The sketchbook had been inside OneDrive (`C:\Users\...\OneDrive\Documents\Arduino`),
which is where all the libraries actually lived. Moving it triggers a OneDrive
"delete 3111 items?" prompt — **choose "Delete all items"**. The files are safe on D:;
choosing "Keep" makes OneDrive re-download them all back onto C:.

### Correction 3 — the IDE keeps its OWN config (this one wastes real time)

`arduino-cli` and the Arduino IDE read **different config files**:

| Tool | Config file |
|---|---|
| arduino-cli | `C:\Users\<you>\AppData\Local\Arduino15\arduino-cli.yaml` |
| Arduino IDE | `C:\Users\<you>\.arduinoIDE\arduino-cli.yaml` |

Change one and the other does not follow. The symptom is a board that compiles
fine from the command line but shows **"NO BOARDS FOUND"** in the IDE's board
picker. Both files must carry the same `directories:` and `board_manager:` blocks.
Both are correct as of this writing; if you ever change one, change both, then
fully restart the IDE.

---

## 5. Hardware

Per the build guide's list, all bought. Two MCUs are in play (see §6):

| # | Part | Role |
|---|---|---|
| 1 | ProMicro **nRF52840** (Nice!Nano compatible, silkscreen `V1940`) | the real target MCU |
| 1b | **ESP32** DevKit (ESP-WROOM-32, CP2102) | debugging second opinion only |
| 2 | **MLX90640BAA** 32x24 thermal array | heat image |
| 3 | HC-SR04 x2 | distance |
| 4 | INMP441 I2S mic | echo recording |
| 5 | 3W 8ohm speaker | chirp |
| 6 | PAM8302 amp | drives the speaker |
| 7 | LiPo + LM2596 buck converter | power |

Also: breadboard, jumpers, 2x 1k and 2x 2k resistors (for the B3 dividers),
**2x 4.7k** (added for I2C pull-ups, see §7), multimeter.

### Safety rules that still apply

1. **Unplug USB before changing any wire.**
2. nRF52840 is a **3.3 V** part. 5 V on a GPIO destroys it.
3. HC-SR04 ECHO is 5 V and **must** go through the 1k/2k divider (Part B3).
   `5V x 2/(1+2) = 3.33V`. The junction between the two resistors is what goes
   to the MCU — not the end of a resistor.
4. INMP441 `L/R` must be tied to GND or the mic outputs nothing.
5. Speaker never connects directly to an MCU pin — always through the PAM8302.

---

## 6. Boards and pin maps

### 6a. nRF52840 ProMicro (the real target)

This is a clone with **no `SDA`/`SCL` silkscreen** — the pads are labelled with raw
port numbers (`O31`, `O29`, `1.15`, ...). Two consequences:

**Board selection:** choose **"Nordic nRF52840 DK"** (`adafruit:nrf52:pca10056`),
*not* Feather nRF52840 Express. Verified by reading the installed core's
`variants/pca10056/variant.cpp`: its `g_ADigitalPinMap` is the identity map, so
Arduino pin number == the P0.xx number printed on the silkscreen (P1.xx = +32).
With the Feather variant the numbers would not line up.

**Pin map:**

| Signal | Board pad | Arduino pin |
|---|---|---|
| MLX90640 SDA | `O31` | 31 |
| MLX90640 SCL | `O29` | 29 |
| MLX90640 VIN | `VCC` | — |
| MLX90640 GND | `GND` | — |

In code the I2C pins must be set explicitly — the variant's defaults (26/27) are
wrong for this board:

```cpp
Wire.setPins(31, 29);   // SDA = P0.31, SCL = P0.29
Wire.begin();
```

**Measured:** `VCC` to `GND` reads **3.7 V** on USB power. That is above the
MLX90640's 3.6 V absolute maximum, so it is a real concern, not a rounding error.
The `VDD` pad on the small 4-pin debug header (`VDD/DIO/CLK/GND`) reads ~0.05 V —
it is not a usable rail, ignore it. **If B2 is retried on the nRF52, feed the
sensor from a proper 3.3 V source, not from `VCC`.**

**Uploading (this board is fiddly):**
- It uses a **UF2 bootloader**; in bootloader mode it mounts as a USB drive named
  `NICENANO` and a COM port appears.
- Normal app mode = one COM port (COM7 here). DFU/bootloader = a different one (COM6).
- Auto touch-reset frequently fails with
  `No data received on serial port` / `Timed out waiting for acknowledgement`.
- **There is no reset button.** To force bootloader mode, briefly short the `RST`
  pad to `GND` **twice in quick succession** (under half a second apart) with a
  jumper wire. Windows will pop an AutoPlay "file transfer" notification for the
  `NICENANO` drive — ignore it, the Arduino Upload button does not need it.
- Then press Upload immediately; the bootloader window is short.

**LED note:** the blue LED is `LED_BUILTIN` and is what sketches control. The red
LED is a hardware/charge indicator and means nothing about firmware. Red+blue
alternating at power-on is the factory bootloader animation, *not* a running sketch.

### 6b. ESP32 DevKit (debug second opinion)

Used only to check whether the MLX90640 problem followed the sensor or the board.
Much easier to work with: labelled `3V3`, labelled GPIOs, and a hardware `EN`
(reset) and `BOOT` button.

| Signal | ESP32 pin |
|---|---|
| MLX90640 SDA | `D21` (GPIO21) |
| MLX90640 SCL | `D22` (GPIO22) |
| MLX90640 VIN | `3V3` |
| MLX90640 GND | `GND` |

Board: **ESP32 Dev Module** (`esp32:esp32:esp32`), port COM8 here.

**CP2102 driver:** Windows showed the device with **Status: Error** and no COM port.
Fixed by installing Silicon Labs' VCP driver
(`CP210x_Windows_Drivers.zip` from silabs.com, `CP210xVCPInstaller_x64.exe`).
After that it enumerates as *"Silicon Labs CP210x USB to UART Bridge (COM8)"*.

**Uploading:** hold **BOOT** before pressing Upload, release once "Connecting..."
appears. Otherwise you get
`Wrong boot mode detected (0x13)! The chip needs to be in download mode.`

**Serial Monitor:** open it first, then press **EN** to reset. Opening the monitor
after boot misses all the startup output — this cost us several confusing
"nothing is printing" rounds.

---

## 7. B2 — MLX90640: the open problem

**Symptom:** `mlx.begin()` returns false ("MLX90640 not found") on both MCUs,
almost always. Once, on the nRF52, it printed `Outlier pixels: 5` and
`MLX90640 found!` — but then every `getFrame()` call failed, so no thermal data
has ever been read.

### What is definitely true

These are measured, not assumed:

1. **The sensor is alive and correctly addressed.** An I2C scan finds a device at
   **0x33**, the MLX90640's default address, repeatedly and on both MCUs.
2. **The sensor holds real data.** Reading its ID registers directly returns
   plausible unique values:
   ```
   Register 0x2408: 0xCEB8
   Register 0x2409: 0x018A
   Register 0x2407: write ok (err=0) but no data returned
   ```
   Not all-zeros, not all-0xFFFF — so it is a genuine, programmed part.
3. **Short reads work. Long reads do not.** 2-byte register reads succeed.
   `mlx.begin()`, which dumps the **1664-byte** calibration EEPROM in 128-byte
   chunks, fails. This is the sharpest clue we have.
4. **The `SET I2C` solder jumper on the module is bridged** — confirmed by
   multimeter continuity (it beeps). The module is in I2C mode, not UART mode.
5. **Power at the sensor is fine** — 3.23 V measured at the MLX90640's own VIN/GND
   pins while running.

### What has been ruled out

Each of these was tried and did **not** fix it:

| Tried | Result |
|---|---|
| Different MCU entirely (nRF52840 -> ESP32) | same failure |
| I2C clock 100 kHz -> 50 kHz | no fix |
| Refresh rate 8 Hz -> 2 Hz | no fix |
| Separate clean supply (LiPo -> LM2596 -> 3.3 V) | no fix |
| Extra settle delay before `begin()` | no fix |
| Retrying `begin()` 10 times in a row | 10/10 failed |
| Re-seating every wire | changed behaviour (see below) but no fix |
| 2x 4.7 k pull-ups on SDA and SCL to 3V3 | big improvement to scans, still no `begin()` |

### The pull-up finding (worth keeping)

Before pull-ups, an I2C scan reported **phantom devices** — 0x07, 0x08, 0x09, 0x10,
0x11, 0x12 — alongside the real 0x33. Phantom low addresses in a scan mean the bus
lines are floating or being held low; the scanner misreads noise as an ACK.

Adding **4.7 k from SDA to 3V3 and 4.7 k from SCL to 3V3** cleaned this up to just
`0x33` repeatedly. This generic MLX90640BAA breakout does not carry adequate
pull-ups of its own, so **keep these two resistors on the final node.** Add this to
the paper's hardware section.

Phantom addresses reappearing later is a sign the sensor is stuck holding the bus
from an aborted transfer — a bus-recovery routine (toggle SCL 9 times with SDA
released) clears it, and one is included in the probe sketch below.

### Where the evidence points

Two candidates remain, and they are distinguishable:

- **(a) A transfer-length / chunking limit** — everything short works, the long
  128-byte chunked EEPROM dump does not.
- **(b) Marginal physical connections** — breadboard contacts or jumper wires that
  survive short transactions but not sustained ones. This is supported by the
  behaviour changing when wires were re-seated, and by one lone success.

Note that `Adafruit_MLX90640`'s `i2c_dev` member is **private**, so the library's
128-byte chunk size cannot be reduced from a sketch. If (a) is confirmed, the fix
means patching the library or driving the Melexis API directly.

### Next step — run the read-size probe

Do this **first**, before any more rewiring. It settles (a) vs (b) with data instead
of another guess. Full sketch is in Appendix B. It does three things: recovers a
stuck bus, tests read sizes 2 -> 250 bytes five times each, and tries the full
1664-byte EEPROM in 32 / 64 / 128-byte chunks.

Read the result like this:

| Probe output | Meaning | Action |
|---|---|---|
| All sizes OK, full EEPROM fails only at 128-byte chunks | (a) chunk limit | patch library to use smaller chunks |
| Fails cleanly above some size (e.g. 32 ok, 64 not) | (a) buffer limit | same, with the known good size |
| Small sizes fail *randomly* too | (b) electrical | stop debugging in software — solder |

The `endTransmission` error codes are informative: `2` = address NACK,
`3` = data NACK, `5` = timeout.

### If it turns out to be (b)

**Solder the four MLX90640 wires directly** (VIN, GND, SCL, SDA) instead of using
the breadboard, or move to a different breadboard and a fresh set of jumpers. The
guide already warns that the assembly should be rigid — hot glue or perfboard —
because sensors shifting between recordings also ruins dataset consistency. Doing
this properly now serves both goals.

---

## 8. Working code

### Appendix A — I2C scanner (the go-to sanity check)

Run this whenever anything seems wrong. `0x33` and nothing else = bus healthy.

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

### Appendix B — read-size probe (run this next)

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

### Appendix C — the B2 test itself (for once the bus is fixed)

ESP32 version. For the nRF52, replace `Wire.begin(21, 22);` with
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

**B2 passes when:** the grid shows room temperature (roughly 20–30), and putting a
hand in front of the sensor makes those pixels jump to about 30–35. Nothing less
counts as a pass — `MLX90640 found!` alone is not enough, as we learned.

### Appendix D — command-line build/upload

Faster than the IDE once set up, and it prints real error messages.

```bash
# nRF52840 (hold RST-to-GND double-tap first if upload times out)
arduino-cli compile --fqbn adafruit:nrf52:pca10056 <sketch-dir>
arduino-cli upload -p COM7 --fqbn adafruit:nrf52:pca10056 <sketch-dir>

# ESP32 (hold BOOT during upload)
arduino-cli compile --fqbn esp32:esp32:esp32 <sketch-dir>
arduino-cli upload -p COM8 --fqbn esp32:esp32:esp32 <sketch-dir>

arduino-cli board list        # which port is which
```

`arduino-cli.exe` is at `C:\Program Files\Arduino CLI\` and may not be on PATH in a
fresh shell.

---

## 9. Firmware still to write (Part C)

The repo already provides `novis_node.ino`, `protocol.h`, `sensors.h`, `crypto.h`.
Two files are ours to write:

- **`firmware/novis_node/sensors.cpp`** — real drivers for all five sensors. The
  guide gives a full reference implementation. The eight `#define` pin numbers at
  the top are examples and **must** be changed to our real wiring; the guide calls
  this the number one cause of "it compiled but nothing works".
- **`firmware/novis_node/crypto.cpp`** — ChaCha20-Poly1305 via the `Crypto` library.
  Nonce = 8-byte counter + 4-byte session salt.

**Honesty note for the paper:** the firmware uses an **all-zero placeholder key** so
node and host interoperate on the bench. That is fine for our experiments and the
paper already says so. Do not describe it as secure.

Note the guide's `sensors.cpp` calls `Wire.begin()` with no arguments — on our
ProMicro clone that will target the wrong pins. It must become
`Wire.setPins(31, 29)` (or whatever B6's final pin table says) before `Wire.begin()`.

---

## 10. Things to record from here on

The guide is right that you will not remember any of this in three months. For
every session write down:

- what was wired to which pin
- what worked and what did not
- **every number you measured** — the measured value, never the expected one

Specifically still owed to the paper:
- the filled-in B6 pin table
- measured current for all five cases in F1 (replaces the estimated 36.5 mA)
- real battery life (predicted 3.3 h — report whatever it actually is)
- the F2 range table
- whether HC-SR04 works at 3.3 V on battery, or whether we needed an RCWL-1601 or
  a boost converter
- that the MLX90640 breakout needs external 4.7 k pull-ups

And start the **ethics approval** paperwork for Part E now — it can take weeks, and
the 12-scene capture cannot legally begin without it. Consent form, face blurring,
and the point that 60 ms echo spectrograms cannot reconstruct speech (a genuine
privacy strength worth stating in the paper).
