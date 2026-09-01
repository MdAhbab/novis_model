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
| B2 | MLX90640 thermal | **PASS** — at full 8 Hz, see section 4 |
| B3 | HC-SR04 x2 | **code ready, compiled clean** — wiring pending, see section 6 |
| B4 | INMP441 mic | not started |
| B5 | PAM8302 + speaker | not started |
| B6 | Full assembly | not started |
| C | `sensors.cpp`, `crypto.cpp` | not started |
| D | Host BLE receive | not started |
| E | 12-scene capture | **start ethics paperwork now** — takes weeks |
| F | Power/range/latency | not started |

B2 took most of two days. Section 4 explains why, because the cause was not
anything the build guide warns about, and the same trap is waiting in B4 and in
Part C. **B3 is next** — section 6 has the pin plan and a compiled, ready-to-flash
test sketch; wiring it up is the only remaining step.

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
# nRF52840 (double-tap RST-to-GND first if upload times out)
arduino-cli compile --fqbn adafruit:nrf52:pca10056 <sketch-dir>
arduino-cli upload -p COM7 --fqbn adafruit:nrf52:pca10056 <sketch-dir>

# ESP32 (hold BOOT during upload)
arduino-cli compile --fqbn esp32:esp32:esp32 <sketch-dir>
arduino-cli upload -p COM8 --fqbn esp32:esp32:esp32 <sketch-dir>

arduino-cli board list      # which port is which
```

---

## 6. Next up — B3: HC-SR04 ultrasonic (wiring pending, code ready)

Not wired yet, but the pin plan and test sketch are done and compile clean for the
nRF52840 (`adafruit:nrf52:pca10056`) — do this next, one sensor at a time as usual.

**The one real danger in Part B.** HC-SR04 ECHO outputs **5 V**; the nRF52840 is
3.3 V-only and 5 V on a GPIO can destroy it permanently. ECHO must go through a
1k/2k voltage divider — TRIG does not need one, it's an output.

```
HC-SR04 ECHO --[1k]--+--[2k]-- GND
                      |
                to nRF52840 ECHO pin      (midpoint = 5V x 2/3 = 3.33V)
```

### Wiring (LEFT sensor first, test, then RIGHT)

Picking free pins that don't collide with the MLX90640's I2C on O31/O29:

| HC-SR04 | Board pad | Notes |
|---|---|---|
| LEFT VCC | 5V / VBUS | USB power for the bench test — see battery note below |
| LEFT GND | GND | |
| LEFT TRIG | `O17` | direct, no divider |
| LEFT ECHO | `O20` | **through the divider** |
| RIGHT VCC | 5V / VBUS | |
| RIGHT GND | GND | |
| RIGHT TRIG | `O22` | direct, no divider |
| RIGHT ECHO | `O24` | **through the divider** |

### Test code (compiled clean, not yet run against real hardware)

```cpp
// Required on this core even though it looks unused — see section 3a's
// "Serial linking" note. Without it: undefined reference to `Serial'.
#include <Adafruit_TinyUSB.h>

#define TRIG_LEFT   17
#define ECHO_LEFT   20
#define TRIG_RIGHT  22
#define ECHO_RIGHT  24

void setup() {
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 5000) delay(10);

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

**PASS condition:** readings track a hand moving toward/away from the sensor, and
match a real ruler within a few mm at 30 cm — same as the guide's B3.

### Then keep going: B4–B6

- **INMP441 `L/R` must be tied to GND** or the mic outputs nothing at all.
- **Speaker never connects directly to an MCU pin** — always through the PAM8302.
- Physical layout matters: mic ~3 cm from speaker, sonars ~20° left and right of
  centre, everything pointing the same way as the thermal array. Keep it rigid.
- On battery there is no 5 V rail, and many HC-SR04 units stop working below ~4.5 V.
  Test ours on battery once B3 passes on USB; if they fail, we need an RCWL-1601 or
  a boost converter — **and we must write down which we used.**
- **Check every remaining module for a hidden onboard MCU before wiring it**, the
  way the MLX90640 turned out to be a GY-MCU90640 (section 4). Look for RX/TX pins,
  a quoted baud rate, or "smart"/"UART" in the product listing.

## 7. Looking further ahead

### Firmware (Part C)

The repo already has `novis_node.ino`, `protocol.h`, `sensors.h`, `crypto.h`.
Two files are ours:

- **`sensors.cpp`** — real drivers for all five sensors. The guide has a full
  reference implementation. Its eight `#define` pin numbers are examples and
  **must** be replaced with our real wiring — the guide calls this the number one
  cause of "it compiled but nothing works". Also note the guide's version calls
  `Wire.begin()` with no arguments; on our ProMicro clone that targets the wrong
  pins, so it needs `Wire.setPins(...)` first. **Carry over the section 4 fixes
  too, or B2 breaks again silently inside the real firmware:** `PS` tied to GND,
  `Wire.setClock(400000)`, and check whether the INMP441 or any other module in
  the final assembly turns out to have its own onboard MCU the same way this one did.
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
