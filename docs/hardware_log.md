# NOVIS Hardware — Build Log & Handoff

**Branch:** `Hardware` · **Covers:** Part B of `docs/NOVIS_Build_Guide.md` · **Updated:** 5 Sept 2026

Read this before touching the hardware. It says what we are building, how far we
got, what is broken, and what has already been tried so nobody repeats it.

> **Board decision (1 Sept 2026): the node MCU is now ESP32-WROOM-32, permanently —
> not just for debugging.** It was already doing double duty as our debug board for
> B2, and after the nRF52840 ProMicro clone's fiddly UF2 bootloader and unreliable
> serial cost more time than the sensors themselves, the team switched for good.
> `docs/NOVIS_Build_Guide.md` has been updated to match. This log has also been
> trimmed of nRF52840-specific debugging detail (section 3a keeps only what the
> paper's methodology section needs) — the full history is in this branch's git
> log if it's ever needed again. Runnable copies of every current test sketch now
> live under `firmware/bench_tests/`, alongside the code shown inline here.

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
| B3 | HC-SR04 x2 | **PASS**, see section 6 |
| B4 | INMP441 mic | **PASS**, see section 7 |
| B5 | PAM8302 + speaker | **PASS**, see section 8 |
| B6 | Full assembly | **in progress** — see `docs/NOVIS_Final_Module_Build.md` |
| C | `sensors.cpp`, `crypto.cpp`, BLE | drivers + crypto **compile-verified** on ESP32; **BLE not started**, see section 9 |
| D | Host BLE receive | not started |
| E | 12-scene capture | **start ethics paperwork now** — takes weeks |
| F | Power/range/latency | not started |

B2 took most of two days. Section 4 explains why, because the cause was not
anything the build guide warns about. **B3, B4 and B5 have since all passed**
(5 Sept 2026) — the sonars, the microphone and the speaker/amp all work.
Sections 6–8 keep the pin assignments, the test code, and the debugging history
for each, because that history is what the paper's methodology section needs.

> **Still to write down:** sections 6–8 below record what was *tried* while
> each of these was failing, but not what finally made each one pass. Whoever
> got them working should add that — it is the most useful thing in this whole
> log for anyone building the second module.

Work has now moved to **B6, the full assembly** — see
`docs/NOVIS_Final_Module_Build.md` for the construction and test procedure.

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

### 3a. nRF52840 ProMicro — abandoned (kept brief; not needed beyond the paper's methodology note)

A Nice!Nano-compatible clone. Three concrete things cost real time and justify
the switch, worth a sentence each in the paper's hardware section:

- **Bootloader friction.** It uses a UF2 bootloader with no reset button —
  entering it required shorting an `RST` pad to `GND` twice quickly, and
  automatic touch-reset from the Arduino IDE failed more often than it worked.
- **Unreliable serial.** Reading output over USB was inconsistent enough that
  progress had to be tracked via LED blink patterns instead of trusting the
  Serial Monitor.
- **Undocumented toolchain quirks.** At least one build failure
  (`undefined reference to 'Serial'`) turned out to be a linking gotcha
  specific to this core, not a wiring or logic bug — the kind of thing that
  costs an afternoon on an already time-constrained build.

None of this recurs on the ESP32, which is why it isn't documented further
here. The full blow-by-blow (exact pin mapping, bootloader procedure, the
`Adafruit_TinyUSB` linking fix) is preserved in this file's git history if it
is ever needed again — see commits before 1 Sept 2026 on the `Hardware`
branch.

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
Phantom extra addresses = floating bus or a stuck sensor. Also saved at
`firmware/bench_tests/i2c_scanner/i2c_scanner.ino`.

```cpp
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  delay(2000);
  Wire.begin(21, 22);
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

### 5b. The B2 test — this is the actual passing configuration

PASSED at 8 Hz / 400 kHz (section 4). Also saved as a runnable sketch at
`firmware/bench_tests/B2_thermal/B2_thermal.ino`.

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

### 5c. Command line build/upload

Faster than the IDE and prints real errors.

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 <sketch-dir>
arduino-cli upload -p COM8 --fqbn esp32:esp32:esp32 <sketch-dir>   # hold BOOT if it doesn't auto-reset
arduino-cli board list      # which port is which
```

---

## 6. B3 — HC-SR04 ultrasonic (PASS)

Both sensors were wired at once here, ahead of the guide's "left first, then
right" order. It worked out, but keep the guide's order on the assembled
module: testing two at once is exactly how you end up unable to tell cross-talk
from a wiring fault.

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

Also saved at `firmware/bench_tests/B3_sonar/B3_sonar.ino`.

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

### Result: PASS

Both sensors work. **Fill in the details** — measured distance vs. tape measure,
and whether anything had to be changed to get there.

Worth keeping from the debugging, because it will look like a fault again next
time: with **no fixed target** in front of the sensors, readings jump around by
metres between consecutive reads (one run showed
`458 -> 1884 -> 99 -> 1888 -> 0 -> 2209` mm on the same sensor a fraction of a
second apart). That is ambient room reflections with nothing to lock onto, not a
broken sensor. Always judge these against a **fixed** target ~30 cm away, where
readings should cluster near 290-310 mm.

## 7. B4 — INMP441 microphone (PASS)

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

Also saved at `firmware/bench_tests/B4_microphone/B4_microphone.ino`.

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

### Result: PASS

The mic picks up real sound — quiet-room peaks stay low and a clap spikes them
clearly above baseline. **Fill in the actual quiet vs. clap numbers you saw.**

For reference, peak levels of ~72,591 to ~661,616 were seen in ordinary room
conditions during testing. That is well inside the 24-bit sample range (max
~8.4 million), and neither of the two failure patterns the build guide warns
about (stuck at exactly 0, or stuck at one huge constant value).

## 8. B5 — PAM8302 + speaker (PASS)

The speaker works. Two findings from getting it there, both worth keeping
because they generalise to any PAM8302 board — and both are the kind of thing
that will silently bite again on the assembled module:

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

Also saved at `firmware/bench_tests/B5_speaker_chirp/B5_speaker_chirp.ino`.

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
    delayMicroseconds(250);   // 20 steps x 250 us = the real 5 ms chirp.
                              // Swap for delay(50) only as a temporary
                              // debugging aid, then put it back.
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
human ear to make the call. Also saved at
`firmware/bench_tests/B5_mic_speaker_echo_test/B5_mic_speaker_echo_test.ino`.

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
    delayMicroseconds(250);   // the real 5 ms chirp - this test has to use
                              // the real duration, or it measures an echo
                              // NOVIS never actually emits.
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

### Status: PASS

`SD` tied to `VIN` (Finding 1) is done, and `VIN` measured 4.8 V. The speaker
now produces sound. **Write down which of the two findings above was actually
the blocker** — that one sentence is what the paper's hardware section needs,
and it tells the next person where to look first.

### Remaining B6 notes — now the active work

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

### Firmware (Part C) — the BLE side is the real remaining work

The repo's `novis_node.ino` and `protocol.h` were written against **Bluefruit**,
which is nRF52-specific — it does not exist for the ESP32. **The BLE/main-loop
side needs a real rewrite for the ESP32's own BLE stack** (`BLEDevice.h`, built
into the `esp32` board package, or `NimBLE-Arduino` for a smaller footprint).
This has **not been started or tested** — do not assume it's a quick swap; the
wire protocol in `host/protocol.py` must still be matched exactly by whatever
ESP32 BLE code replaces `novis_node.ino`.

The two files that were "ours to write" are further along than that:

- **`sensors.cpp`** — a combined draft of all four sensor drivers (thermal,
  sonar x2, mic/I2S, chirp), using the real B6 pin plan and every section 4
  MLX90640 fix (`Wire.setClock(400000)`, matching what wiring `PS` to GND
  requires), **compiles clean for ESP32** as a single unit — no symbol or
  resource conflicts between the four drivers. Saved at
  `firmware/bench_tests/sensors_combined_compile_check/`. Still not run as a
  combined unit on real hardware, and not yet moved into
  `firmware/novis_node/sensors.cpp` itself. **Now unblocked** — B2-B5 have all
  passed individually, so the merge can go ahead once B6 assembly confirms
  they still work together on one board.
- **`crypto.cpp`** — ChaCha20-Poly1305 via the `Crypto` library (Rhys
  Weatherley). **Compiles and runs on ESP32, confirmed** (it seals a test
  frame and prints the output length on boot). Saved at
  `firmware/bench_tests/crypto_compile_check/`.

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
