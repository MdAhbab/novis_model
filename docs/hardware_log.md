# NOVIS Hardware — Build Log & Handoff

**Branch:** `Hardware` · **Covers:** Part B of `docs/NOVIS_Build_Guide.md` · **Updated:** 1 Sept 2026

Read this before touching the hardware. It says what we are building, how far we
got, what is broken, and what has already been tried so nobody repeats it.

> **Board decision (1 Sept 2026): the node MCU is now ESP32-WROOM-32, permanently —
> not just for debugging.** It was already doing double duty as our debug board for
> B2 (section 3b as it used to be), and after the nRF52840 ProMicro clone's fiddly
> UF2 bootloader and unreliable serial cost more time than the sensors themselves,
> the team switched for good. `docs/NOVIS_Build_Guide.md` has been updated to match.
> Section 3 below keeps the nRF52840 notes — they're hard-won and still useful if
> anyone ever needs that board again — but relabelled as historical, not current.

---

## 1. What we are building, and why this way

NOVIS makes a picture of a room **without a camera**.

```
MLX90640 thermal + 2x HC-SR04 sonar + INMP441 mic/speaker echo
        |
    ESP32 node   <- only senses, packs, encrypts. No AI here.
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
| B1 | Board alive (Blink) | **PASS** (on the nRF52840, before the board switch) |
| B2 | MLX90640 thermal | **PASS** — ESP32, full 8 Hz, see section 4 |
| B3 | HC-SR04 x2 | **wired, testing** — readings unstable, see section 6 |
| B4 | INMP441 mic | **wired, testing** — signal present, pass not yet confirmed, see section 7 |
| B5 | PAM8302 + speaker | **wired, no sound yet** — actively debugging, see section 8 |
| B6 | Full assembly | not started |
| C | `sensors.cpp`, `crypto.cpp` | not started — needs an ESP32 BLE rewrite, see section 9 |
| D | Host BLE receive | not started |
| E | 12-scene capture | **start ethics paperwork now** — takes weeks |
| F | Power/range/latency | not started |

B2 took most of two days. Section 4 explains why, because the cause was not
anything the build guide warns about. **B3, B4, and B5 are all wired and being
tested right now** (1 Sept 2026) — none has a clean, confirmed PASS yet. Sections
6–8 have the real pin assignments, the actual test code, and exactly what's been
tried on each so far.

### Toolchain

Arduino IDE 2.3.10 + Arduino CLI 1.5.1. Cores: `esp32:esp32` 3.3.11 (current
target), `adafruit:nrf52` 1.7.0 (kept installed, no longer the target — see the
board decision above). Libraries: Adafruit MLX90640 1.1.2, Adafruit BusIO 1.17.4,
Crypto (Rhys Weatherley) 0.4.0.

**The build guide's board URL is dead.** Part A3 says to use
`https://www.adafruit.com/package_adafruit_index.json` — it 404s. Use instead:

```
https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
https://espressif.github.io/arduino-esp32/package_esp32_index.json
```

---

## 3. The two boards, and the switch from one to the other

We started on the **nRF52840** (the original target). When the thermal sensor
would not work, we moved it to an **ESP32** to answer one question: *does the
problem follow the sensor, or the board?* It followed the sensor — same failure
on both — which is why the ESP32 first shows up in this document as just a
debugging tool.

It didn't stay a debugging tool. Across B1–B2 the nRF52840's UF2 bootloader,
unreliable native-USB serial, and the undocumented `Adafruit_TinyUSB` linking
gotcha (below) ate more time than any sensor did. The ESP32's plain CP2102
serial port and real EN/BOOT buttons made every single test in this log faster
to run. **As of 1 Sept 2026 the ESP32 is the permanent node MCU** — section 3a
below is kept as a historical/reference record, not as the current board.

### 3a. nRF52840 ProMicro — abandoned, kept for reference

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

**Reading serial from this board is unreliable.** Scripted reads (PowerShell,
`arduino-cli monitor`) returned nothing repeatedly even while the sketch was
clearly running. Use the **Arduino IDE Serial Monitor**, and note the port changes
between DFU and app mode, so re-select it after every upload. Because of this, we
added **LED blink patterns as progress markers** in the test sketches — e.g. 6 fast
blinks = `setup()` reached, 2 medium = `Wire.begin()` done, 3 slow = sensor found,
fast strobe forever = sensor not found. When serial is dead, the LED still tells you
exactly how far the code got. Worth keeping that trick for the rest of Part B.

**A sketch with no libraries will not link — this looks like a Serial bug but isn't.**
On this core, the global `Serial` object (USB CDC) is defined inside the bundled
`Adafruit_TinyUSB` library, and Arduino only links a library if the sketch includes
one of its headers. B2's sketch used `Serial` fine because `Adafruit_MLX90640.h`
pulls TinyUSB in as a side effect. A plain sketch that only calls `Serial.begin()` /
`pinMode()` / `pulseIn()` — exactly what B3, B4 and B5 need — has nothing to pull it
in, and fails with `undefined reference to 'Serial'` /
`Adafruit_USBD_CDC::begin(unsigned long)`. Fix: add
`#include <Adafruit_TinyUSB.h>` at the top, even though nothing in the sketch
appears to call it directly.

### 3b. ESP32 DevKit — the node MCU (current)

ESP-WROOM-32 with CP2102. Labelled `3V3`, labelled GPIOs, real `EN` (reset) and
`BOOT` buttons. This is the board every section from here on assumes.

| MLX90640 | ESP32 pin |
|---|---|
| SDA | `D21` (GPIO21) |
| SCL | `D22` (GPIO22) |
| VIN | `3V3` |
| GND | `GND` |

Board: **ESP32 Dev Module** (`esp32:esp32:esp32`), COM8 here.

**Trade-off to write into the paper:** the ESP32 is a WiFi+BLE combo chip and
draws meaningfully more current than the nRF52840 (a BLE-only radio) — expect
tens of mA at idle and well over 100 mA during WiFi/BLE activity, versus the
nRF52840's single-digit-mA idle draw. All of the paper's estimated power/battery
numbers (Part F1 of the build guide) were sized around the nRF52840 and are now
invalid. They must be re-measured on the ESP32, not adjusted by guesswork.

- **CP2102 driver:** Windows first showed the device as **Status: Error** with no
  COM port. Fixed by installing Silicon Labs' VCP driver (`CP210x_Windows_Drivers.zip`
  → `CP210xVCPInstaller_x64.exe`).
- **Upload:** hold **BOOT**, press Upload, release when "Connecting..." appears.
  Otherwise: `Wrong boot mode detected (0x13)! The chip needs to be in download mode.`
- **Serial Monitor:** open it *first*, then press **EN** to reset. Opening it after
  boot misses all the startup prints — this caused several false "nothing is
  printing" panics.

---

## 4. B2 — MLX90640: solved, and why it took so long

**Status: PASS.** The sensor now streams a full 32x24 grid at **8 Hz over 400 kHz
I2C**. Room reads ~27 C and a hand in frame shows 33-37 C.

There were **two separate faults stacked on top of each other**. Both are worth
understanding, because the first one will bite again in B4 and Part C.

### Fault 1 — our module is not a plain breakout (this was the real one)

We have a **GY-MCU90640**, not a bare MLX90640 breakout. It carries **its own
onboard STM32**, and by default that STM32 is the **I2C master** of the MLX90640,
reading it continuously and streaming the result out over **UART at 460800 baud**.
The giveaways were there from the start and we missed them: the module has `RX`/`TX`
pins, and the product page quotes a *baud rate* — a plain I2C sensor has no baud rate.

So for two days we were a **second master on a bus that already had one**. Every
symptom follows from that:

| Symptom | Cause |
|---|---|
| Scan found 0x33 | the sensor chip really is on the bus |
| 2-byte register reads worked | short transfers sometimes won arbitration |
| 128-byte EEPROM reads always failed | the STM32's own traffic cut into long transfers |
| Phantom addresses 0x07-0x17 in scans | another master driving the lines mid-scan |
| Sometimes `found`, mostly not | pure timing luck |
| Nothing electrical ever fixed it | it was never an electrical problem |

**The fix: tie the `PS` pin to `GND`, then power-cycle.** That puts the module into
I2C passthrough mode and takes the STM32 off the bus. `PS` is sampled **only at
power-up**, so after wiring it you must **unplug and replug USB** — a reset or EN
press does nothing. We had left `PS` floating the entire time.

### Fault 2 — I2C too slow for the frame rate (error -8)

With `PS` grounded, `begin()` succeeded immediately but every `getFrame()` returned
**-8**. Reading the library source, -8 is literally "too many retries":
`getFrame()` reads a frame, clears the data-ready flag, re-reads status, and gives
up after 5 rounds if the flag keeps coming back set.

The arithmetic explains it. One frame is 1664 bytes:

| I2C clock | time to read a frame | frame arrives every (8 Hz) | keeps up? |
|---|---|---|---|
| 100 kHz | ~150 ms | 125 ms | no — always behind |
| 400 kHz | ~37 ms | 125 ms | yes, comfortably |

At 100 kHz a new frame was always ready before we finished reading the last one, so
the flag never cleared. **Raising the clock to 400 kHz fixed it.**

If -8 ever comes back, you can attack it from either end: raise the I2C clock, or
lower the sensor with `mlx.setRefreshRate(MLX90640_2_HZ)`. Prefer raising the clock
— **NOVIS is designed around 8 Hz thermal** and the protocol and throughput numbers
assume it. If we ever ship at a lower refresh rate, that has to be written down,
because it changes the paper's numbers.

### Final working configuration

| Setting | Value |
|---|---|
| `PS` pin | tied to GND (power-cycle after wiring) |
| I2C clock | 400 kHz |
| Refresh rate | 8 Hz (`MLX90640_8_HZ`) |
| Resolution | 18-bit (`MLX90640_ADC_18BIT`) |
| Mode | chess (`MLX90640_CHESS`) |
| Pull-ups | 2x 4.7k, SDA and SCL to 3V3 |

### Keep the pull-ups

Before we added them, an I2C scan showed phantom devices; with 4.7k from SDA to 3V3
and 4.7k from SCL to 3V3 the scan cleaned up to just `0x33`. We have not tested
whether they are still strictly required now that the STM32 is off the bus, and
there is no reason to find out — **leave them on the final node.** The article this
build follows claims these breakouts have adequate onboard pull-ups; ours did not.
Note this in the paper's hardware section.

### What it was NOT — do not re-test these

All of the following were tried and none of them was the cause. Recorded so nobody
burns another day on them:

swapping the MCU (nRF52840 <-> ESP32), lowering the clock to 50 kHz, dropping the
refresh rate to 2 Hz, powering the sensor from a separate LiPo + LM2596 3.3 V
supply, adding settle delays before `begin()`, retrying `begin()` ten times, and
re-seating every wire.

Two of these *appeared* to help — a slower clock and re-seated wires — which is
exactly what made the diagnosis so slow. Both were only changing how often we lost
the arbitration race, not fixing it. **Lesson: when the same setup gives different
answers run to run, suspect contention on the bus before suspecting bad solder.**

### One more thing to carry forward

Read the product page and the module silkscreen before assuming a part is what the
guide assumes. `RX`, `TX` and `PS` pins on something described as an I2C sensor mean
there is a microcontroller in the way. The INMP441 (B4) and the final assembly
(B6/C) deserve the same check.

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

### 5b. Read-size probe — kept for reference, not what fixed B2

Written while we still thought the fault was electrical (see section 4 for what it
actually was — a second I2C master on the bus, fixed by grounding `PS`). Never got
a conclusive run before the real cause was found. Keeping it here because it is a
genuinely useful pattern for a future "short reads work, long reads don't" bug —
just don't expect it to explain *this* one.

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

### 5c. The B2 test — this is the actual passing configuration

ESP32 version, PASSED at 8 Hz / 400 kHz (section 4). On nRF52, replace
`Wire.begin(21, 22);` with `Wire.setPins(31, 29); Wire.begin();` — the clock and
refresh rate lines stay the same.

```cpp
#include <Wire.h>
#include <Adafruit_MLX90640.h>

Adafruit_MLX90640 mlx;
float frame[32 * 24];

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("Starting MLX90640 test...");

  Wire.begin(21, 22);      // PS must already be tied to GND (power-cycled after wiring)

  // 400 kHz is required to keep up with the 8 Hz refresh rate below: one frame
  // is 1664 bytes (~150 ms at 100 kHz, ~37 ms at 400 kHz) but a new frame
  // arrives every 125 ms. Too slow here and getFrame() returns -8 forever.
  Wire.setClock(400000);

  if (!mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire)) {
    Serial.println("ERROR: MLX90640 not found. Check wiring, and that PS is tied to GND.");
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

**PASS confirmed:** grid reads ~27 C at room temperature, a hand in frame reads
33-37 C, sustained at 8 Hz. `MLX90640 found!` on its own is not a pass — `getFrame()`
has to succeed too, and for a while it didn't (error -8, see section 4).

### 5d. Command line build/upload

Faster than the IDE and prints real errors.

```bash
# ESP32 (current board — hold BOOT during upload if it doesn't auto-reset)
arduino-cli compile --fqbn esp32:esp32:esp32 <sketch-dir>
arduino-cli upload -p COM8 --fqbn esp32:esp32:esp32 <sketch-dir>

# nRF52840 (abandoned, kept for reference — double-tap RST-to-GND first if upload times out)
arduino-cli compile --fqbn adafruit:nrf52:pca10056 <sketch-dir>
arduino-cli upload -p COM7 --fqbn adafruit:nrf52:pca10056 <sketch-dir>

arduino-cli board list      # which port is which
```

---

## 6. B3 — HC-SR04 ultrasonic (wired, testing — not a confirmed PASS)

**Both sensors are wired already**, ahead of the guide's "left first, then right"
order — worth going back and isolating them if the trouble below doesn't clear up
quickly, since testing two at once is exactly how you end up unable to tell
cross-talk from a wiring fault.

**The one real danger in Part B.** HC-SR04 ECHO outputs **5 V**; the ESP32 is
3.3 V-only and 5 V on a GPIO can destroy it permanently. ECHO must go through a
1k/2k voltage divider — TRIG does not need one, it's an output.

```
HC-SR04 ECHO --[1k]--+--[2k]-- GND
                      |
                to ESP32 ECHO pin      (midpoint = 5V x 2/3 = 3.33V)
```

### Wiring (as built)

Pins chosen to avoid the MLX90640's I2C on GPIO21/22:

| HC-SR04 | ESP32 pin | Notes |
|---|---|---|
| LEFT VCC | 5V / VIN | USB power for the bench test |
| LEFT GND | GND | |
| LEFT TRIG | **GPIO16** | direct, no divider |
| LEFT ECHO | **GPIO17** | **through the divider** |
| RIGHT VCC | 5V / VIN | |
| RIGHT GND | GND | |
| RIGHT TRIG | **GPIO18** | direct, no divider |
| RIGHT ECHO | **GPIO19** | **through the divider** |

### Test code (compiles clean, running on real hardware)

```cpp
#define TRIG_LEFT   16
#define ECHO_LEFT   17
#define TRIG_RIGHT  18
#define ECHO_RIGHT  19

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  pinMode(TRIG_LEFT, OUTPUT);
  pinMode(ECHO_LEFT, INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);

  Serial.println("HC-SR04 test starting...");
}

// Returns distance in millimetres, or 0 if nothing was detected.
uint16_t readRange(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);       // datasheet asks for a 10 us pulse
  digitalWrite(trigPin, LOW);

  unsigned long duration = pulseIn(echoPin, HIGH, 30000UL);  // 30ms timeout, ~5m
  if (duration == 0) return 0;

  return (uint16_t)((duration * 343UL) / 2000UL);  // mm, round trip
}

void loop() {
  uint16_t left = readRange(TRIG_LEFT, ECHO_LEFT);
  delay(60);   // gap so the two sensors don't hear each other's pings (cross-talk)
  uint16_t right = readRange(TRIG_RIGHT, ECHO_RIGHT);

  Serial.print("Left: ");  Serial.print(left);  Serial.print(" mm   ");
  Serial.print("Right: "); Serial.print(right); Serial.println(" mm");

  delay(200);
}
```

(No `Adafruit_TinyUSB.h` needed here — that gotcha was specific to the abandoned
nRF52 core, see section 3a. Plain `Serial` links fine on ESP32.)

### Current result: unstable readings, not yet a PASS

With no fixed target in front of the sensors, both LEFT and RIGHT jump around
with no visible pattern between consecutive reads — e.g. one run showed
`458 -> 1884 -> 99 -> 1888 -> 0 -> 2209` mm on the same sensor a fraction of a
second apart. That is not the expected behaviour (real readings should be
*noisy by a few mm*, not jump by metres), and it has **not yet been tested against
a fixed target**, so it isn't clear yet whether this is a real fault or just
ambient room reflections with nothing to lock onto.

**Next step, not yet done:** hold a hand or book at a fixed ~30 cm in front of
ONE sensor and confirm 5-6 consecutive readings cluster near 290-310 mm before
judging pass/fail. If it's still erratic with a real, fixed target:
- re-seat the divider wiring (loose breadboard contact is the usual suspect, as
  it was for B2)
- increase the 60 ms gap between LEFT and RIGHT reads — cross-talk from a bigger
  room won't clear in 60 ms
- isolate to one sensor at a time as the guide originally intended

## 7. B4 — INMP441 microphone (wired, testing — signal present, PASS not confirmed)

The guide calls this "the hardest step in the build" for a reason we hit
immediately: **the nRF52 register-level I2S code in the build guide is entirely
non-portable.** It talks directly to `NRF_I2S`, a peripheral that does not exist
on the ESP32. This had to be rewritten from scratch using the ESP32's own I2S
driver (`driver/i2s.h`), not adapted line-by-line.

### Wiring (as built)

Pin choice comes straight from the vendor's own product page for this exact
compatible module — trusted as authoritative for this specific part:

| INMP441 pin | ESP32 pin |
|---|---|
| VDD | 3V3 |
| GND | GND |
| SCK (bit clock) | **GPIO14** |
| WS (word select) | **GPIO15** |
| SD (data out) | **GPIO32** |
| **L/R** | **GND** — required, or the mic outputs nothing |

### Test code (ESP32 I2S driver, compiles and runs)

```cpp
#include <driver/i2s.h>

#define I2S_SCK_PIN   14   // bit clock
#define I2S_WS_PIN    15   // word select
#define I2S_SD_PIN    32   // data in from the microphone
#define I2S_PORT      I2S_NUM_0

#define SAMPLES 256
static int32_t rxBuffer[SAMPLES];

void i2sBegin() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = SAMPLES,
    .use_apll = false
  };
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK_PIN,
    .ws_io_num = I2S_WS_PIN,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD_PIN
  };
  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  Serial.println("INMP441 microphone test...");
  i2sBegin();
}

void loop() {
  size_t bytesRead = 0;
  i2s_read(I2S_PORT, rxBuffer, sizeof(rxBuffer), &bytesRead, portMAX_DELAY);
  int samples = bytesRead / sizeof(int32_t);

  int32_t peak = 0;
  for (int i = 0; i < samples; i++) {
    int32_t s = rxBuffer[i] >> 8;   // 24-bit sample sitting in a 32-bit word
    if (s > peak)  peak = s;
    if (-s > peak) peak = -s;
  }

  Serial.print("Peak level: ");
  Serial.println(peak);
  delay(100);
}
```

### Current result: readings in the thousands-to-hundred-thousands range, ambiguous

Observed peak levels ranged from ~72,591 to ~661,616 during ordinary room
conditions (no controlled quiet/loud comparison done yet). This is well within
the 24-bit sample range (max ~8.4 million) and is *not* the specific failure
pattern the guide warns about (stuck at exactly 0, or stuck at one huge constant
value) — so the mic is very likely picking up real sound. But without a proper
before/after comparison this isn't a confirmed PASS.

**Next step, not yet done:** record ~10 s of peak levels in a silent room as a
baseline, then clap once sharply near the mic and confirm the peak spikes to
clearly above baseline before settling back down. That comparison, not the raw
numbers alone, is what the guide's PASS condition actually means.

## 8. B5 — PAM8302 + speaker (wired, no confirmed sound yet — actively debugging)

Two real findings so far, both worth keeping regardless of how this resolves,
because they generalise to any PAM8302 board:

### Finding 1 — the `SD` (shutdown) pin must be tied high

Our PAM8302A breakout (the Adafruit PAM8302A layout: `A+ / SD / Vin / Gnd` along
the bottom edge, `+` / `-` speaker output pads at the top labelled `4-8R`/`Amp`,
a trim pot for volume) breaks out an `SD` pin separately. **Left floating, the
amp stays in shutdown and produces no sound no matter what signal `A+` gets.**
Fix: wire `SD` to the same `VIN` net the board is already powered from. This is
just tapping the same rail twice — no conflict with the rest of the wiring.

### Finding 2 — check solder joints, not just schematic correctness

The speaker itself ships with a JST-PH2.0 2-pin connector, which does not mate
with this PAM8302 board's plated through-holes. The connector has to be cut off
and the bare wires (red = OUT+, black = OUT-, standard convention — reversed
polarity is harmless for a single speaker, just an inaudible phase flip) attached
directly. **A wire looped through the hole and twisted, but not soldered, is a
real suspect for "everything checks out but there's still no sound"** — it can
look connected and still have poor or intermittent contact. Solder it, or at
minimum verify continuity with a multimeter, before ruling out the amp itself.

### Wiring (as built)

| PAM8302 pin | Connect to |
|---|---|
| VIN | 3.3V or 5V — measured **4.8 V** in our build, within spec |
| GND | GND |
| A+ | **GPIO4** |
| A- | GND |
| **SD** | **VIN** (tap the same rail — see Finding 1) |
| + (OUT+) | Speaker red wire |
| - (OUT-) | Speaker black wire |

### Test code — chirp only

```cpp
#define SPEAKER_PIN 4

void setup() {
  Serial.begin(115200);
  pinMode(SPEAKER_PIN, OUTPUT);
  Serial.println("Chirp test. Listen for a short rising tone every 2 seconds.");
}

// Emit a chirp that sweeps from 1 kHz up to 8 kHz.
void emitChirp() {
  const int steps = 20;
  for (int i = 0; i < steps; i++) {
    float t = (float)i / (float)(steps - 1);
    int freq = (int)(1000.0f * powf(8.0f, t));
    tone(SPEAKER_PIN, freq);
    delay(50);   // TEMPORARY: long/loud for testing. The real design uses
                 // delayMicroseconds(250) for a 5 ms chirp — change back once
                 // sound is confirmed, or the paper's chirp-duration number is wrong.
  }
  noTone(SPEAKER_PIN);
}

void loop() {
  emitChirp();
  delay(2000);
}
```

### Objective test — mic + speaker together (don't trust your ears alone)

Human hearing is a bad instrument for confirming a 5-50 ms chirp exists — this is
exactly the guide's next step (B5 "test the microphone and speaker together")
brought forward because "I can't hear it" was too ambiguous to debug against.
This combines the B4 and B5 code so the mic reports a number instead of asking a
human ear to make the call:

```cpp
#include <driver/i2s.h>

#define SPEAKER_PIN   4
#define I2S_SCK_PIN   14
#define I2S_WS_PIN    15
#define I2S_SD_PIN    32
#define I2S_PORT      I2S_NUM_0
#define SAMPLES       256

static int32_t rxBuffer[SAMPLES];

void i2sBegin() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = SAMPLES,
    .use_apll = false
  };
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK_PIN,
    .ws_io_num = I2S_WS_PIN,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD_PIN
  };
  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
}

int32_t readMicPeak() {
  size_t bytesRead = 0;
  i2s_read(I2S_PORT, rxBuffer, sizeof(rxBuffer), &bytesRead, portMAX_DELAY);
  int samples = bytesRead / sizeof(int32_t);
  int32_t peak = 0;
  for (int i = 0; i < samples; i++) {
    int32_t s = rxBuffer[i] >> 8;
    if (s > peak) peak = s;
    if (-s > peak) peak = -s;
  }
  return peak;
}

void emitChirp() {
  const int steps = 20;
  for (int i = 0; i < steps; i++) {
    float t = (float)i / (float)(steps - 1);
    int freq = (int)(1000.0f * powf(8.0f, t));
    tone(SPEAKER_PIN, freq);
    delay(50);
  }
  noTone(SPEAKER_PIN);
}

void setup() {
  Serial.begin(115200);
  pinMode(SPEAKER_PIN, OUTPUT);
  i2sBegin();
  Serial.println("Chirp + mic combined test starting...");
}

void loop() {
  int32_t before = readMicPeak();
  Serial.print("Mic peak BEFORE chirp: ");
  Serial.println(before);

  emitChirp();

  int32_t after = readMicPeak();
  Serial.print("Mic peak DURING/AFTER chirp: ");
  Serial.println(after);
  Serial.println("-----");

  delay(1500);
}
```

Read it as: a clear spike in "AFTER" versus "BEFORE" means the speaker is making
sound (even if too quiet/short to hear) and the mic can hear it — a real PASS for
both B4 and B5's echo test at once. No spike means the fault is still in the
amp/speaker chain, not human hearing.

### Also useful: the "pop test" to isolate amp+speaker from the MCU signal

Momentarily touch the `A+` wire to `VIN` (power on, one quick touch) — a working
amp+speaker chain produces an audible "pop" or "click" with no code involved at
all. Pop = amp and speaker are fine, the problem is upstream (GPIO4 wiring or the
`tone()` signal). No pop = the problem is downstream (OUT+/OUT- connection or the
speaker itself) — go straight back to Finding 2 above.

### Status as of last test

`SD` tied to `VIN` (Finding 1) is done. `VIN` confirmed at 4.8 V. Still no audible
sound. The wire-wrap-not-soldered connection (Finding 2) is the leading suspect
and has not yet been confirmed fixed. Next step is the pop test, then either the
combined mic+speaker test above or a straight continuity check on OUT+/OUT-.

### Remaining B6 notes, once B3-B5 all pass individually

- Physical layout matters: mic ~3 cm from speaker, sonars ~20° left and right of
  centre, everything pointing the same way as the thermal array. Keep it rigid.
- On battery there is no 5 V rail, and many HC-SR04 units stop working below ~4.5 V.
  Test ours on battery once B3 passes on USB; if they fail, we need an RCWL-1601 or
  a boost converter — **and we must write down which we used.**
- **Check every remaining module for a hidden onboard MCU before wiring it**, the
  way the MLX90640 turned out to be a GY-MCU90640 (section 4). Look for RX/TX pins,
  a quoted baud rate, or "smart"/"UART" in the product listing. (INMP441, the 3W/8Ω
  speaker, and this PAM8302 have all been checked against their product pages —
  none of them hide an MCU.)
- When wiring B6, re-run each individual B2-B5 test sketch once everything shares
  one breadboard and one common GND — a module that passed alone can fail once
  everything is powered together if grounds aren't actually common.

## 9. Looking further ahead

### Firmware (Part C) — bigger than "fill in two files" now

The repo's `novis_node.ino` and `protocol.h` were written against **Bluefruit**,
which is nRF52-specific — it does not exist for the ESP32. **Part C is no longer
"two files are ours"; the BLE/main-loop side needs a real rewrite for the ESP32's
own BLE stack** (`BLEDevice.h`, built into the `esp32` board package, or
`NimBLE-Arduino` for a smaller footprint). This has **not been started or tested**
— do not assume it's a quick swap; the wire protocol in `host/protocol.py` must
still be matched exactly by whatever ESP32 BLE code replaces `novis_node.ino`.

What's still expected to carry over largely unchanged:

- **`sensors.cpp`** — real drivers for all five sensors, following section 6-8's
  code above (ESP32 pins: I2C on 21/22, HC-SR04 on 16/17/18/19, I2S mic on
  14/15/32, chirp on 4). **Carry over every section 4 MLX90640 fix or B2 breaks
  again silently inside the real firmware:** `PS` tied to GND, `Wire.setClock(400000)`,
  4.7k pull-ups on the final PCB/board too.
- **`crypto.cpp`** — ChaCha20-Poly1305 via the `Crypto` library (Rhys Weatherley).
  This library is written to be portable across AVR/SAMD/ESP32/nRF52, so it should
  compile for ESP32 unchanged, but **we have not actually compiled or run it on
  the ESP32 ourselves yet** — verify before assuming it works.

**For the paper:** the firmware uses an **all-zero placeholder key** so node and
host talk on the bench. Fine for our experiments, and the paper already says so.
Do not describe it as secure.

### Numbers we still owe the paper

Write down what you actually measure, never what you expected:

- the filled-in B6 pin table
- current for all five cases in F1 — **the guide's 36.5 mA estimate is for the
  nRF52840 and no longer applies at all now that the node is an ESP32** (WiFi+BLE
  combo chip, meaningfully higher draw — see section 3b). Needs fresh estimates
  before it's even worth measuring against, not just fresh measurements.
- real battery life on the ESP32 (the guide's predicted 3.3 h assumed the
  nRF52840 and is not a useful reference point anymore — report the truth,
  whatever it turns out to be)
- the F2 range table (1–10 m)
- HC-SR04 at 3.3 V: worked, or needed RCWL-1601 / boost converter?
- that the MLX90640 module needs external 4.7k pull-ups, its `PS` pin tied to GND,
  and 400 kHz I2C to sustain 8 Hz — all three are in section 4

### Part E — start the paperwork now

Ethics approval can take weeks and the 12-scene capture cannot legally start
without it. Needed: consent from everyone in the room, a simple consent form, and
face blurring before data leaves the recording machine. Split the dataset **by
scene, never by frame** — frames from the same room in both train and test will be
caught by reviewers. Worth stating in the paper: the 60 ms echo recordings are
stored as spectrograms and speech cannot be recovered from them — a genuine
privacy strength.
