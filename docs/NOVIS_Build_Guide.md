# NOVIS — Complete Build, Code & Experiment Guide

**For the NOVIS team. Everything you need is in this one document.**

Project: NOVIS (Non-Optical Visual Inference System)
Code repository: https://github.com/MdAhbab/novis_model
Last updated: 26 August 2026

---

## Table of Contents

0. [Read this first](#0-read-this-first)
1. [The big picture](#1-the-big-picture)
2. [What you need](#2-what-you-need)
3. [Part A — Set up your computer](#part-a--set-up-your-computer)
4. [Part B — Build the hardware, one sensor at a time](#part-b--build-the-hardware-one-sensor-at-a-time)
5. [Part C — Write the firmware](#part-c--write-the-firmware)
6. [Part D — Host side: receive the data](#part-d--host-side-receive-the-data)
7. [Part E — Collect real data](#part-e--collect-real-data)
8. [Part F — Experiments and measurements](#part-f--experiments-and-measurements)
9. [Part G — Command cheat sheet](#part-g--command-cheat-sheet)
10. [Troubleshooting](#10-troubleshooting)
11. [Who does what](#11-who-does-what)

---

## 0. Read this first

### What this document is

This is a step-by-step guide to build the NOVIS sensor node, write its
firmware, connect it to a computer, and collect real data. You should not
need any other document while working. Every command and every piece of
code you need is written here.

### How to use it

Work through the parts **in order**. Do not skip ahead. Each step ends with
a test. **Do not move to the next step until the test passes.** This is the
single most important rule in this guide. If you wire all five sensors at
once and nothing works, you will not know which one is broken. If you wire
one sensor, test it, then add the next, you always know exactly what broke.

### A note on honesty

Some numbers in our paper are still *estimates* (battery life, power draw,
range). The whole point of building the hardware is to replace those
estimates with **real measured numbers**. When you measure something, write
down what you actually measured — never write down what you expected.

---

## 1. The big picture

### What NOVIS does

NOVIS reconstructs a picture of a room **without using a camera**.

A small battery-powered device (we call it the **node**) sits in a room. It
has three kinds of sensors, none of which is a camera:

| Sensor | What it senses | Think of it as |
|---|---|---|
| **MLX90640** thermal array | Heat, as a 32×24 grid of temperatures | A very blurry heat picture |
| **HC-SR04** ×2 ultrasonic | Distance to the nearest surface | A tape measure that works by sound |
| **INMP441** mic + speaker | Echoes of a short chirp sound | How a bat "sees" |

The node does **no thinking**. It only:
1. Reads the sensors
2. Packs the readings into small packets ("frames")
3. Encrypts each packet
4. Sends them over Bluetooth to a computer or phone (the **host**)

The host runs our AI model, **NOVISNet**, which turns those sensor readings
into four pictures at once:
- a grayscale image
- a depth map (how far away everything is)
- a guessed colour image
- a confidence map (how much to trust the guessed colour)

### The flow, in one line

```
Sensors → nRF52840 → encrypt → Bluetooth → Host PC → NOVISNet → images
```

### Why the node is "dumb"

The node has a tiny battery. Running an AI model would drain it in minutes.
So the node only senses and transmits, and the host — which has a big
battery and a real processor — does all the heavy work. This is called
**split computing**, and it is one of our paper's contributions.

---

## 2. What you need

### Hardware — all of this is already bought ✅

| # | Part | What it does |
|---|---|---|
| 1 | **nRF52840** Pro Micro board (Nice!Nano compatible) | The brain. Reads sensors, encrypts, sends Bluetooth |
| 2 | **MLX90640** 32×24 thermal array | Heat image |
| 3 | **HC-SR04** ultrasonic module ×2 | Distance measurement |
| 4 | **INMP441** I2S microphone | Records echoes |
| 5 | **3W 8Ω speaker** | Emits the chirp sound |
| 6 | **PAM8302** audio amplifier | Makes the chirp loud enough |
| 7 | **LiPo battery** (150 mAh or similar) | Power |

### Also needed (basic workshop items)

- Breadboard and jumper wires (male-to-male, male-to-female)
- Resistors for the voltage divider: **2× 1 kΩ and 2× 2 kΩ** (see Part B3 — this is important)
- A multimeter (for the power measurement experiment in Part F)
- A USB cable that supports **data**, not only charging
- A smartphone with a camera (for the real data capture in Part E)

### Software

- **Windows PC** with Python 3.11 or 3.12
- **Arduino IDE** (version 2.x)
- **Git**
- An **NVIDIA GPU** — only needed on the machine that trains the model. The
  hardware and firmware work described in Parts A–F needs no GPU.

---

## Part A — Set up your computer

### A1. Get the code

Open PowerShell or Command Prompt and run:

```bash
git clone https://github.com/MdAhbab/novis_model.git
```

```bash
cd novis_model
```

Now create a Python virtual environment. This keeps our project's packages
separate from the rest of your computer, so nothing conflicts.

```bash
py -3.12 -m venv .venv
```

```bash
.venv\Scripts\activate
```

After this, your command prompt line should start with `(.venv)`. That means
the environment is active. **You must run this `activate` command every time
you open a new terminal window for this project.**

Now install the packages:

```bash
python -m pip install --upgrade pip
```

If you have an NVIDIA GPU (needed only for training):

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

If you do **not** have an NVIDIA GPU (fine for hardware/firmware work):

```bash
pip install torch
```

Then install everything else:

```bash
pip install -r requirements.txt
```

### A2. Check that it works — no hardware needed

This is important. Before touching any wires, confirm the software side runs.

```bash
python tests/test_smoke.py
```

You should see `ALL SMOKE TESTS PASSED` at the end.

Now test the full host pipeline — this builds a fake sensor frame, encrypts
it, splits it into Bluetooth-sized pieces, puts it back together, decrypts
it, and runs the model on it. Exactly what will happen with real hardware:

```bash
python tests/test_host_pipeline.py
```

Then run the whole thing end to end with fake sensor data:

```bash
python -m host.live_infer --source synthetic --config configs/base.yaml
```

This writes a file at `results/live_output.npz`. If this works, your
computer is ready. The images will look like noise — that is expected,
because no trained model exists yet.

> **Why this matters:** if something breaks later with real hardware, you
> now know for certain the problem is the hardware, not the software.

### A3. Set up the Arduino IDE

1. Download and install **Arduino IDE 2.x** from arduino.cc
2. Open it. Go to **File → Preferences**
3. In the box labelled **"Additional boards manager URLs"**, paste this:

   ```
   https://www.adafruit.com/package_adafruit_index.json
   ```

4. Click OK
5. Go to **Tools → Board → Boards Manager**
6. Search for **"Adafruit nRF52"** and click **Install**. This takes several
   minutes — it downloads a full compiler toolchain. Be patient.
7. When it finishes, go to **Tools → Board → Adafruit nRF52 Boards** and
   select your board. If you have a Nice!Nano-compatible Pro Micro nRF52840,
   choose **"Nice!Nano"** if listed, otherwise **"Adafruit Feather nRF52840
   Express"** works for most clones.

### A4. Install the Arduino libraries

Go to **Tools → Manage Libraries**, then search and install each of these:

| Library to search for | Used for |
|---|---|
| `Adafruit MLX90640` | Thermal sensor |
| `Adafruit BusIO` | Required by the above (usually installs automatically) |
| `Crypto` by Rhys Weatherley | ChaCha20-Poly1305 encryption |

The Bluetooth library (Bluefruit) comes with the board package — you do not
need to install it separately.

---

## Part B — Build the hardware, one sensor at a time

### B0. Safety rules — read before touching anything

1. **Always unplug the USB cable before changing any wire.** Rewiring a
   powered board is the most common way to destroy it.
2. **The nRF52840 is a 3.3 V chip.** Putting 5 V on any of its pins can
   permanently destroy it. The HC-SR04 outputs 5 V. See step B3 — you
   **must** build a voltage divider.
3. **Double-check power and ground before plugging in.** Reversing VCC and
   GND destroys most modules instantly.
4. **Add one sensor at a time.** Test it. Only then add the next.

### B1. Step 1 — The board alone

**Goal:** confirm the board is alive and you can upload code to it.

1. Plug the nRF52840 board into your PC with the USB cable
2. In Arduino IDE, go to **Tools → Port** and select the port that appears
3. Go to **File → Examples → 01.Basics → Blink**
4. Click the **Upload** arrow

**Test passes if:** the small LED on the board blinks on and off, once per
second.

**If nothing happens:** double-tap the reset button on the board quickly.
This puts most nRF52840 boards into bootloader mode — a drive should appear
on your computer. Then try uploading again.

---

### B2. Step 2 — The thermal sensor (MLX90640)

This is our most important sensor, so we do it first.

#### Wiring

The MLX90640 uses **I2C**, a two-wire communication bus.

| MLX90640 pin | Connect to nRF52840 |
|---|---|
| VIN (or VCC) | **3.3 V** |
| GND | GND |
| SDA | SDA pin |
| SCL | SCL pin |

> **Finding SDA and SCL on your board:** look at the silkscreen printing on
> the board, or search online for "[your board name] pinout". On the
> nRF52840 any pin can be used for I2C, but the board defines default SDA
> and SCL pins — use those, they are simplest.

#### Test code

Create a new sketch (**File → New**), paste this in, and upload:

```cpp
#include <Wire.h>
#include <Adafruit_MLX90640.h>

Adafruit_MLX90640 mlx;
float frame[32 * 24];

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);   // wait for the Serial Monitor to open

  Serial.println("Starting MLX90640 test...");

  if (!mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire)) {
    Serial.println("ERROR: MLX90640 not found. Check your wiring.");
    while (1) delay(10);
  }

  Serial.println("MLX90640 found!");
  mlx.setMode(MLX90640_CHESS);
  mlx.setResolution(MLX90640_ADC_18BIT);
  mlx.setRefreshRate(MLX90640_8_HZ);   // 8 frames per second, as our design says
}

void loop() {
  if (mlx.getFrame(frame) != 0) {
    Serial.println("Failed to read a frame");
    delay(500);
    return;
  }

  // Print the temperature grid as text, one row per line
  for (int y = 0; y < 24; y++) {
    for (int x = 0; x < 32; x++) {
      Serial.print(frame[y * 32 + x], 1);
      Serial.print(" ");
    }
    Serial.println();
  }
  Serial.println("-----");
  delay(1000);
}
```

Open **Tools → Serial Monitor** and set the speed to **115200**.

**Test passes if:** you see a grid of numbers, roughly 20 to 30 (room
temperature in Celsius). **Now put your hand in front of the sensor** — the
numbers where your hand is should jump to around 30–35. That is your first
thermal image. This is the moment the project becomes real.

**If it says "MLX90640 not found":**
- Check SDA and SCL are not swapped
- Check the sensor is on 3.3 V, not 5 V
- Try adding 4.7 kΩ pull-up resistors from SDA to 3.3 V and SCL to 3.3 V
  (most breakout boards already have these built in, but some clones do not)

---

### B3. Step 3 — The ultrasonic sensors (HC-SR04 ×2)

⚠️ **This step has the one real danger in the whole build. Read it fully
before wiring.**

#### The 5 V problem

The HC-SR04 is designed for **5 V**. Its ECHO pin outputs a **5 V** signal.
The nRF52840's pins accept a maximum of **3.3 V**. Connecting the ECHO pin
directly to the nRF52840 **can permanently destroy the chip**.

**The fix: a voltage divider.** This is two resistors that cut the 5 V down
to about 3.3 V. You need one for each HC-SR04, so two in total.

#### Building the voltage divider

For each sensor:

```
HC-SR04 ECHO pin ----[ 1 kΩ ]----+----> to nRF52840 input pin
                                  |
                               [ 2 kΩ ]
                                  |
                                 GND
```

The point where the two resistors meet is what goes to the nRF52840. This
gives 5 V × (2 / (1+2)) = **3.33 V**. Safe.

The TRIG pin needs no divider — that is an output from the nRF52840 to the
sensor, and 3.3 V is enough to trigger it.

#### Powering the HC-SR04

Here is a real issue you should know about now, not discover later:

- **On USB power:** your board has a 5 V pin (often labelled `VBUS`,
  `RAW`, or `5V`). Use that for the HC-SR04's VCC. Works perfectly.
- **On battery power:** the board only produces 3.3 V. There is no 5 V.
  Many HC-SR04 modules become unreliable or stop working below about 4.5 V.

**What to do:** do all bench testing on USB power first. When you move to
battery, test whether your specific HC-SR04 units still work at 3.3 V — some
clones do. If they do not, you have two options: buy an **RCWL-1601** (a
pin-compatible 3.3 V version of the HC-SR04), or add a small **3.3 V → 5 V
boost converter** module. **Write down which option you used** — this goes
in the paper's hardware section.

#### Wiring

| HC-SR04 pin | Connect to |
|---|---|
| VCC | 5 V (USB) — see note above |
| GND | GND |
| TRIG | any free GPIO pin (direct, no resistors) |
| ECHO | **through the voltage divider** → any free GPIO pin |

Do the **left** sensor first. Test it. Then add the **right** one.

#### Test code

```cpp
// Change these to whichever pins you actually used
#define TRIG_LEFT   2
#define ECHO_LEFT   3
#define TRIG_RIGHT  4
#define ECHO_RIGHT  5

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  pinMode(TRIG_LEFT, OUTPUT);
  pinMode(ECHO_LEFT, INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);

  Serial.println("HC-SR04 test starting...");
}

// Returns distance in millimetres, or 0 if nothing was detected
uint16_t readRange(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);       // the datasheet asks for a 10 microsecond pulse
  digitalWrite(trigPin, LOW);

  // Wait for the echo. Time out after 30 ms (about 5 metres).
  unsigned long duration = pulseIn(echoPin, HIGH, 30000UL);
  if (duration == 0) return 0;   // no echo came back

  // Sound travels about 0.343 mm per microsecond.
  // Divide by 2 because the sound goes out AND comes back.
  return (uint16_t)((duration * 343UL) / 2000UL);
}

void loop() {
  uint16_t left  = readRange(TRIG_LEFT, ECHO_LEFT);
  delay(60);   // wait so the two sensors do not hear each other's pings
  uint16_t right = readRange(TRIG_RIGHT, ECHO_RIGHT);

  Serial.print("Left: ");  Serial.print(left);  Serial.print(" mm   ");
  Serial.print("Right: "); Serial.print(right); Serial.println(" mm");

  delay(200);
}
```

**Test passes if:** you see distance numbers that change correctly when you
move your hand closer and further. Hold your hand about 30 cm away — you
should read roughly 300. Measure with a real ruler and compare.

> **Note the 60 ms delay between the two sensors.** Without it, the right
> sensor can hear the left sensor's ping and report a wrong distance. This
> is called cross-talk. Our firmware reads them one after the other for
> exactly this reason.

---

### B4. Step 4 — The microphone (INMP441)

**This is the hardest step in the build.** Give it time and do not panic if
it does not work on the first try.

The INMP441 uses **I2S**, a digital audio protocol. It needs three signal
wires plus power.

#### Wiring

| INMP441 pin | Connect to |
|---|---|
| VDD | 3.3 V |
| GND | GND |
| SD (data out) | any free GPIO |
| WS (or LRCL) | any free GPIO |
| SCK (or BCLK) | any free GPIO |
| L/R | **GND** (this selects the left channel) |

> The `L/R` pin **must** be connected to GND. If it is left floating, the
> microphone may output nothing at all.

#### Test code

The nRF52840 has a built-in I2S peripheral. This code configures it
directly.

```cpp
#include <Arduino.h>
#include <nrf.h>

// Change these to the pins you actually used
#define I2S_SCK_PIN   6    // bit clock
#define I2S_LRCK_PIN  7    // word select
#define I2S_SD_PIN    8    // data in from the microphone

#define SAMPLES 256
static int32_t rxBuffer[SAMPLES];

void i2sBegin() {
  NRF_I2S->CONFIG.MODE     = I2S_CONFIG_MODE_MODE_Master     << I2S_CONFIG_MODE_MODE_Pos;
  NRF_I2S->CONFIG.RXEN     = I2S_CONFIG_RXEN_RXEN_Enabled    << I2S_CONFIG_RXEN_RXEN_Pos;
  NRF_I2S->CONFIG.TXEN     = I2S_CONFIG_TXEN_TXEN_Disabled   << I2S_CONFIG_TXEN_TXEN_Pos;
  NRF_I2S->CONFIG.MCKEN    = I2S_CONFIG_MCKEN_MCKEN_Enabled  << I2S_CONFIG_MCKEN_MCKEN_Pos;

  // Master clock 32 MHz / 31 = 1.032 MHz;  1.032 MHz / 64 = 16.1 kHz sample rate.
  // This is close enough to our target of 16 kHz.
  NRF_I2S->CONFIG.MCKFREQ  = I2S_CONFIG_MCKFREQ_MCKFREQ_32MDIV31 << I2S_CONFIG_MCKFREQ_MCKFREQ_Pos;
  NRF_I2S->CONFIG.RATIO    = I2S_CONFIG_RATIO_RATIO_64X          << I2S_CONFIG_RATIO_RATIO_Pos;

  NRF_I2S->CONFIG.SWIDTH   = I2S_CONFIG_SWIDTH_SWIDTH_24Bit  << I2S_CONFIG_SWIDTH_SWIDTH_Pos;
  NRF_I2S->CONFIG.ALIGN    = I2S_CONFIG_ALIGN_ALIGN_Left     << I2S_CONFIG_ALIGN_ALIGN_Pos;
  NRF_I2S->CONFIG.FORMAT   = I2S_CONFIG_FORMAT_FORMAT_I2S    << I2S_CONFIG_FORMAT_FORMAT_Pos;
  NRF_I2S->CONFIG.CHANNELS = I2S_CONFIG_CHANNELS_CHANNELS_Left << I2S_CONFIG_CHANNELS_CHANNELS_Pos;

  NRF_I2S->PSEL.SCK   = (I2S_SCK_PIN  << I2S_PSEL_SCK_PIN_Pos);
  NRF_I2S->PSEL.LRCK  = (I2S_LRCK_PIN << I2S_PSEL_LRCK_PIN_Pos);
  NRF_I2S->PSEL.SDIN  = (I2S_SD_PIN   << I2S_PSEL_SDIN_PIN_Pos);
  NRF_I2S->PSEL.MCK   = 0x80000000;   // master clock output not used
  NRF_I2S->PSEL.SDOUT = 0x80000000;   // no output

  NRF_I2S->RXD.PTR      = (uint32_t)rxBuffer;
  NRF_I2S->RXTXD.MAXCNT = SAMPLES;

  NRF_I2S->ENABLE = 1;
  NRF_I2S->TASKS_START = 1;
}

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  Serial.println("INMP441 microphone test...");
  i2sBegin();
}

void loop() {
  // Wait until one buffer of samples has been received
  NRF_I2S->EVENTS_RXPTRUPD = 0;
  NRF_I2S->RXD.PTR = (uint32_t)rxBuffer;
  while (NRF_I2S->EVENTS_RXPTRUPD == 0) { }
  NRF_I2S->EVENTS_RXPTRUPD = 0;

  // Find the loudest sample in this buffer, so we can see if sound is detected
  int32_t peak = 0;
  for (int i = 0; i < SAMPLES; i++) {
    int32_t s = rxBuffer[i] >> 8;   // 24-bit sample sitting in a 32-bit word
    if (s > peak)  peak = s;
    if (-s > peak) peak = -s;
  }

  Serial.print("Peak level: ");
  Serial.println(peak);
  delay(100);
}
```

**Test passes if:** the "Peak level" number is small and steady when the room
is quiet, and jumps up sharply when you clap or speak near the microphone.

**If the number is always 0:**
- Check `L/R` is connected to GND
- Check SD, WS, and SCK are not swapped
- Try changing `SWIDTH` from `24Bit` to `16Bit`

**If the number is always huge and does not change:** the data pin is
probably floating — check the SD wire.

---

### B5. Step 5 — The speaker and amplifier (PAM8302)

#### Wiring

The PAM8302 sits between the nRF52840 and the speaker. It makes a weak
signal loud enough to be useful.

| PAM8302 pin | Connect to |
|---|---|
| VIN | 3.3 V (or 5 V from USB for a louder chirp) |
| GND | GND |
| A+ (audio in +) | any free GPIO on the nRF52840 |
| A− (audio in −) | GND |
| OUT+ | speaker terminal 1 |
| OUT− | speaker terminal 2 |

> Do **not** connect the speaker directly to the nRF52840 pin without the
> amplifier. The chip cannot supply enough current and you may damage it.

#### Test code

```cpp
#define SPEAKER_PIN 9   // change to your pin

void setup() {
  Serial.begin(115200);
  pinMode(SPEAKER_PIN, OUTPUT);
  Serial.println("Chirp test. Listen for a short rising tone every 2 seconds.");
}

// Emit a 5 ms chirp that sweeps from 1 kHz up to 8 kHz.
// We do it in 20 small steps; each step is a slightly higher tone.
void emitChirp() {
  const int steps = 20;
  for (int i = 0; i < steps; i++) {
    float t = (float)i / (float)(steps - 1);     // goes from 0.0 to 1.0
    int freq = (int)(1000.0f * powf(8.0f, t));   // 1000 Hz up to 8000 Hz
    tone(SPEAKER_PIN, freq);
    delayMicroseconds(250);                      // 20 steps x 250 us = 5 ms
  }
  noTone(SPEAKER_PIN);
}

void loop() {
  emitChirp();
  delay(2000);
}
```

**Test passes if:** you hear a short, quiet "tick" or "chirp" every two
seconds. It is very short (5 milliseconds), so listen carefully in a quiet
room. If you cannot hear it, temporarily change `delayMicroseconds(250)` to
`delay(50)` — that makes a much longer, obvious sweep for testing. **Change
it back to 250 afterwards.**

#### Now test the microphone and speaker together

This is the real echo test. Upload a sketch that emits a chirp and then
immediately prints the microphone peak levels. Point the node at a wall
about 1 metre away. You should see the peak level spike right after each
chirp — that spike is the echo coming back. **That is echolocation
working.**

---

### B6. Step 6 — Full assembly

Now connect everything at once, on one breadboard.

**Suggested pin plan** — fill in the right-hand column with the pins you
actually used, and keep this table. You will need it for the firmware and
for the paper's hardware section.

| Signal | Goes to which nRF52840 pin? |
|---|---|
| MLX90640 SDA | ____ |
| MLX90640 SCL | ____ |
| HC-SR04 left TRIG | ____ |
| HC-SR04 left ECHO (via divider) | ____ |
| HC-SR04 right TRIG | ____ |
| HC-SR04 right ECHO (via divider) | ____ |
| INMP441 SCK | ____ |
| INMP441 WS / LRCL | ____ |
| INMP441 SD | ____ |
| Speaker / PAM8302 input | ____ |

**Physical layout matters.** Our design assumes:
- The microphone sits about **3 cm from the speaker**
- The two ultrasonic sensors point **left and right of centre**, roughly
  20 degrees each way
- All sensors point in the **same forward direction** as the thermal array

Try to keep the assembly rigid — hot glue or a small piece of perfboard
helps. If sensors shift between recordings, your data becomes inconsistent.

**Test:** re-run each individual test sketch from B2 to B5, one at a time,
with everything now connected. All four must still pass. If one breaks now
that everything is connected, you likely have a power or ground problem —
check that every module shares a common GND.

---

## Part C — Write the firmware

Now we replace the placeholder code in the repository with the real code
you just tested.

### What is already done for you

The repository at `firmware/novis_node/` already contains all the difficult
structural code:

| File | What it does | Status |
|---|---|---|
| `novis_node.ino` | Main loop, Bluetooth, timing | ✅ Done |
| `protocol.h` | Packet format | ✅ Done |
| `sensors.h` | Function definitions | ✅ Done |
| `sensors.cpp` | Sensor reading | ❌ **You write this** |
| `crypto.h` | Encryption definitions | ✅ Done |
| `crypto.cpp` | Encryption | ❌ **You write this** |

So your job is only two files. Everything else already works.

### C1. Write `sensors.cpp`

Open `firmware/novis_node/sensors.cpp` and **replace its entire contents**
with this. This is your tested code from Part B, fitted into the shape the
rest of the firmware expects.

```cpp
// NOVIS sensor drivers — real implementations.
#include "sensors.h"

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_MLX90640.h>
#include <nrf.h>

// ---------------------------------------------------------------
// PIN ASSIGNMENTS — change these to match your actual wiring (Part B6)
// ---------------------------------------------------------------
#define TRIG_LEFT     2
#define ECHO_LEFT     3
#define TRIG_RIGHT    4
#define ECHO_RIGHT    5
#define I2S_SCK_PIN   6
#define I2S_LRCK_PIN  7
#define I2S_SD_PIN    8
#define SPEAKER_PIN   9

// ---------------------------------------------------------------
// Thermal
// ---------------------------------------------------------------
static Adafruit_MLX90640 mlx;
static float mlxFrame[NOVIS_THERMAL_PIXELS];
static bool  mlxOk = false;

// ---------------------------------------------------------------
// Microphone (I2S)
// ---------------------------------------------------------------
#define I2S_CHUNK 256
static int32_t i2sBuf[I2S_CHUNK];

static void i2sBegin() {
  NRF_I2S->CONFIG.MODE     = I2S_CONFIG_MODE_MODE_Master       << I2S_CONFIG_MODE_MODE_Pos;
  NRF_I2S->CONFIG.RXEN     = I2S_CONFIG_RXEN_RXEN_Enabled      << I2S_CONFIG_RXEN_RXEN_Pos;
  NRF_I2S->CONFIG.TXEN     = I2S_CONFIG_TXEN_TXEN_Disabled     << I2S_CONFIG_TXEN_TXEN_Pos;
  NRF_I2S->CONFIG.MCKEN    = I2S_CONFIG_MCKEN_MCKEN_Enabled    << I2S_CONFIG_MCKEN_MCKEN_Pos;
  NRF_I2S->CONFIG.MCKFREQ  = I2S_CONFIG_MCKFREQ_MCKFREQ_32MDIV31 << I2S_CONFIG_MCKFREQ_MCKFREQ_Pos;
  NRF_I2S->CONFIG.RATIO    = I2S_CONFIG_RATIO_RATIO_64X        << I2S_CONFIG_RATIO_RATIO_Pos;
  NRF_I2S->CONFIG.SWIDTH   = I2S_CONFIG_SWIDTH_SWIDTH_24Bit    << I2S_CONFIG_SWIDTH_SWIDTH_Pos;
  NRF_I2S->CONFIG.ALIGN    = I2S_CONFIG_ALIGN_ALIGN_Left       << I2S_CONFIG_ALIGN_ALIGN_Pos;
  NRF_I2S->CONFIG.FORMAT   = I2S_CONFIG_FORMAT_FORMAT_I2S      << I2S_CONFIG_FORMAT_FORMAT_Pos;
  NRF_I2S->CONFIG.CHANNELS = I2S_CONFIG_CHANNELS_CHANNELS_Left << I2S_CONFIG_CHANNELS_CHANNELS_Pos;

  NRF_I2S->PSEL.SCK   = (I2S_SCK_PIN  << I2S_PSEL_SCK_PIN_Pos);
  NRF_I2S->PSEL.LRCK  = (I2S_LRCK_PIN << I2S_PSEL_LRCK_PIN_Pos);
  NRF_I2S->PSEL.SDIN  = (I2S_SD_PIN   << I2S_PSEL_SDIN_PIN_Pos);
  NRF_I2S->PSEL.MCK   = 0x80000000;
  NRF_I2S->PSEL.SDOUT = 0x80000000;

  NRF_I2S->RXD.PTR      = (uint32_t)i2sBuf;
  NRF_I2S->RXTXD.MAXCNT = I2S_CHUNK;

  NRF_I2S->ENABLE = 1;
  NRF_I2S->TASKS_START = 1;
}

// Read one chunk of I2S samples into i2sBuf. Blocks until the chunk is full.
static void i2sReadChunk() {
  NRF_I2S->RXD.PTR = (uint32_t)i2sBuf;
  NRF_I2S->EVENTS_RXPTRUPD = 0;
  uint32_t guard = 0;
  while (NRF_I2S->EVENTS_RXPTRUPD == 0) {
    if (++guard > 2000000UL) break;   // safety: never hang forever
  }
  NRF_I2S->EVENTS_RXPTRUPD = 0;
}

// ---------------------------------------------------------------
// Chirp emitter
// ---------------------------------------------------------------
static void emitChirp() {
  const int steps = 20;
  for (int i = 0; i < steps; i++) {
    float t = (float)i / (float)(steps - 1);
    int freq = (int)(1000.0f * powf(8.0f, t));   // 1 kHz -> 8 kHz, logarithmic
    tone(SPEAKER_PIN, freq);
    delayMicroseconds(250);
  }
  noTone(SPEAKER_PIN);
}

// ---------------------------------------------------------------
// Public functions used by novis_node.ino
// ---------------------------------------------------------------

bool sensors_begin(void) {
  Wire.begin();
  Wire.setClock(400000);   // fast I2C, needed to keep up at 8 Hz

  mlxOk = mlx.begin(MLX90640_I2CADDR_DEFAULT, &Wire);
  if (mlxOk) {
    mlx.setMode(MLX90640_CHESS);
    mlx.setResolution(MLX90640_ADC_18BIT);
    mlx.setRefreshRate(MLX90640_8_HZ);
  }

  pinMode(TRIG_LEFT,  OUTPUT);
  pinMode(ECHO_LEFT,  INPUT);
  pinMode(TRIG_RIGHT, OUTPUT);
  pinMode(ECHO_RIGHT, INPUT);
  pinMode(SPEAKER_PIN, OUTPUT);
  digitalWrite(TRIG_LEFT,  LOW);
  digitalWrite(TRIG_RIGHT, LOW);

  i2sBegin();

  return mlxOk;
}

bool sensors_read_thermal(int16_t thermal[NOVIS_THERMAL_PIXELS]) {
  if (!mlxOk) return false;
  if (mlx.getFrame(mlxFrame) != 0) return false;

  // The protocol wants int16 in centi-Celsius: 25.0 C becomes 2500.
  for (int i = 0; i < NOVIS_THERMAL_PIXELS; i++) {
    float c = mlxFrame[i];
    if (c < -300.0f) c = -300.0f;      // clamp so it always fits in int16
    if (c >  300.0f) c =  300.0f;
    thermal[i] = (int16_t)(c * 100.0f);
  }
  return true;
}

bool sensors_capture_echo(int16_t echo[NOVIS_ECHO_SAMPLES]) {
  // Send the chirp, then record the echo window that follows.
  emitChirp();

  int written = 0;
  while (written < NOVIS_ECHO_SAMPLES) {
    i2sReadChunk();
    for (int i = 0; i < I2S_CHUNK && written < NOVIS_ECHO_SAMPLES; i++) {
      // The INMP441 gives a 24-bit sample inside a 32-bit word.
      // Shift down to 16 bits, which is what our protocol expects.
      int32_t s24 = i2sBuf[i] >> 8;    // now a 24-bit value
      int32_t s16 = s24 >> 8;          // now a 16-bit value
      if (s16 >  32767) s16 =  32767;
      if (s16 < -32768) s16 = -32768;
      echo[written++] = (int16_t)s16;
    }
  }
  return true;
}

// Read one HC-SR04. Returns millimetres, or 0 if no echo came back.
static uint16_t readRange(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  unsigned long duration = pulseIn(echoPin, HIGH, 30000UL);
  if (duration == 0) return 0;
  return (uint16_t)((duration * 343UL) / 2000UL);
}

bool sensors_read_sonar(uint16_t *left, uint16_t *right, uint8_t *status) {
  uint16_t l = readRange(TRIG_LEFT, ECHO_LEFT);
  delayMicroseconds(3000);           // small gap so the sensors do not interfere
  uint16_t r = readRange(TRIG_RIGHT, ECHO_RIGHT);

  *left  = l;
  *right = r;
  *status = (uint8_t)((l > 0 ? 0x01 : 0x00) | (r > 0 ? 0x02 : 0x00));
  return true;
}
```

> **Important:** update the eight `#define` lines at the top to match the
> pins you actually wired in Part B6. This is the number one cause of "it
> compiled but nothing works".

### C2. Write `crypto.cpp`

Create a **new file** in the same folder called `crypto.cpp` and paste this:

```cpp
// NOVIS AEAD implementation using ChaCha20-Poly1305.
// Library: "Crypto" by Rhys Weatherley (install via Arduino Library Manager).
#include "crypto.h"

#include <Arduino.h>
#include <ChaChaPoly.h>
#include <string.h>

static uint8_t sessionKey[NOVIS_KEY_BYTES];
static uint8_t sessionSalt[NOVIS_SALT_BYTES];

void crypto_set_session(const uint8_t key[NOVIS_KEY_BYTES],
                        const uint8_t salt[NOVIS_SALT_BYTES]) {
  memcpy(sessionKey,  key,  NOVIS_KEY_BYTES);
  memcpy(sessionSalt, salt, NOVIS_SALT_BYTES);
}

size_t crypto_seal(uint64_t counter, const uint8_t *frame, size_t len,
                   uint8_t *out) {
  // The nonce is: 8 bytes of counter, then 4 bytes of session salt.
  // Because the counter always increases, the nonce is never reused.
  uint8_t nonce[12];
  for (int i = 0; i < 8; i++) nonce[i] = (uint8_t)(counter >> (8 * i));
  memcpy(nonce + 8, sessionSalt, NOVIS_SALT_BYTES);

  ChaChaPoly cipher;
  cipher.clear();
  cipher.setKey(sessionKey, NOVIS_KEY_BYTES);
  cipher.setIV(nonce, 12);

  // Output layout: counter(8) || ciphertext(len) || tag(16)
  memcpy(out, nonce, NOVIS_COUNTER_BYTES);
  cipher.encrypt(out + NOVIS_COUNTER_BYTES, frame, len);
  cipher.computeTag(out + NOVIS_COUNTER_BYTES + len, NOVIS_TAG_BYTES);

  return NOVIS_COUNTER_BYTES + len + NOVIS_TAG_BYTES;
}
```

> **Security note for the paper:** the firmware currently uses an all-zero
> placeholder key so that the node and the host can talk to each other on
> the bench. This is fine for our experiments. Before any real deployment,
> the key must come from a proper handshake. Our paper already says this
> honestly — do not claim the placeholder is secure.

### C3. Upload the firmware

1. In Arduino IDE, open `firmware/novis_node/novis_node.ino`
2. Select your board and port
3. Click **Upload**

**Test passes if:** the board appears in your phone's Bluetooth scanner (or
in an app like "nRF Connect") with the name **`NOVIS-Node`**.

---

## Part D — Host side: receive the data

### D1. Install the extra packages

Make sure your virtual environment is active (`(.venv)` shows in your
prompt), then:

```bash
pip install cryptography bleak
```

- `cryptography` does the decryption
- `bleak` is the Bluetooth library

### D2. Test again without hardware

Always confirm the software path works before blaming the hardware:

```bash
python -m host.live_infer --source synthetic --config configs/base.yaml
```

### D3. Connect to the real node

Power on the node, then:

```bash
python -m host.live_infer --source ble --config configs/base.yaml
```

The program scans for a device named `NOVIS-Node`, connects, and prints a
line for each frame it receives.

**Test passes if:** you see frames arriving and being decoded. Wave your
hand in front of the thermal sensor — the numbers in the printout should
change.

**This is the biggest milestone in the whole project.** When this works, the
full chain — real sensors → encryption → Bluetooth → decryption → AI model —
is running end to end.

### D4. The browser interface

For a nicer view:

```bash
python run.py
```

This starts a web server and opens a browser page where you can see the
reconstruction live. The first time you run it, it builds the frontend,
which takes a few minutes.

> With no trained model yet, the images will look like noise and the page
> shows an "untrained weights" warning. That is expected. The point right
> now is confirming that data flows.

---

## Part E — Collect real data

This is our project's most valuable contribution. Every other paper in this
area uses simulated data. We will have **real** data.

### E1. Build the capture rig

We need to record, at the same moment:
- what the node's sensors see
- what a real camera sees (this is our "correct answer" for training)

Mount the node and a smartphone on a **rigid** bracket — a piece of wood, a
plastic sheet, anything that does not bend. Both must point in the **same
direction**, with the camera lens about **4 cm** from the thermal sensor.

**Do not let them move relative to each other after this point.** If they
shift, all recordings before and after the shift are inconsistent.

### E2. Align the camera to the sensor

The thermal sensor sees a 55° × 35° view. Your phone camera sees a different
view. We need to crop the phone image so both see the same thing.

**How to do it, once:**

1. Put four warm objects in the room — mugs of hot water work well, or four
   people standing in the corners of the view
2. Take one thermal reading and one phone photo at the same time
3. Look at both images. Find the same four warm points in each
4. Note the pixel positions in the phone photo of those four points
5. Use those to work out the crop rectangle in the phone photo that matches
   the thermal view
6. **Write those crop numbers down.** Use the same crop for every recording.

### E3. The recording script

Create a new file `record_capture.py` in the repository root and paste this
in. It saves each moment as one `.npz` file containing all sensor readings
plus the reference photo.

```python
"""Record synchronized NOVIS sensor data plus a reference photo.

Usage:
    python record_capture.py --scene office_1 --minutes 5

Press Ctrl+C to stop early. Each recorded moment becomes one .npz file in
data/real_capture/<scene>/.
"""

import argparse
import asyncio
import time
from pathlib import Path

import numpy as np

from host import protocol as P
from host.assemble import FrameAssembler
from host.crypto import Session
from host.receiver import scan_and_connect   # see note below


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True, help="name of this scene, e.g. office_1")
    ap.add_argument("--minutes", type=float, default=5.0)
    ap.add_argument("--rate", type=float, default=2.0,
                    help="how many tuples to save per second")
    args = ap.parse_args()

    out_dir = Path("data/real_capture") / args.scene
    out_dir.mkdir(parents=True, exist_ok=True)

    assembler = FrameAssembler(device="cpu")
    saved = 0
    t_end = time.time() + args.minutes * 60
    interval = 1.0 / args.rate
    t_next = time.time()

    print(f"Recording scene '{args.scene}' for {args.minutes} minutes...")
    print("Take phone photos continuously. Press Ctrl+C to stop.")

    async for frame in scan_and_connect():
        assembler.update(frame)

        now = time.time()
        if now >= t_next and assembler.ready():
            batch = assembler.model_input()
            np.savez_compressed(
                out_dir / f"tuple_{saved:06d}.npz",
                thermal=batch["thermal"].numpy()[0],
                echo=batch["echo"].numpy()[0],
                sonar=batch["sonar"].numpy()[0],
                mask=batch["mask"].numpy()[0],
                wall_time=now,
            )
            saved += 1
            t_next = now + interval
            if saved % 20 == 0:
                print(f"  saved {saved} tuples")

        if now > t_end:
            break

    print(f"Done. Saved {saved} tuples to {out_dir}")


if __name__ == "__main__":
    asyncio.run(main())
```

> **Note:** the exact function name in `host/receiver.py` may differ. Open
> that file, see what it provides, and adjust the import line. This is a
> five-minute job and is expected — the repository's receiver was written
> for live inference, not recording.

**How to match photos to sensor data:** record the phone's clock time when
you start, and save `wall_time` in each `.npz` (the script above already
does). Later, match each `.npz` to the phone photo taken closest in time.

### E4. The capture plan

Record **12 different scenes**, about **5 minutes each**:

| Scene type | How many |
|---|---|
| Office rooms | 3 |
| Corridors | 3 |
| Lab / classroom | 3 |
| Living room / home | 3 |

For each scene:
- Move the rig slowly around the room, do not hold it still
- Include people at different distances (1 m, 3 m, 5 m)
- Include some empty views with no people
- Try both lights-on and lights-off (our system should work in the dark —
  prove it)

**Very important:** split the data **by scene**, never by frame. That means
whole scenes go into the test set — not a random selection of frames. If
frames from the same room appear in both training and testing, the model
looks better than it really is, and reviewers will catch it.

### E5. Privacy and consent — do this properly

We will be recording real people in real rooms. This must be handled
correctly or the paper cannot be published.

1. **Ask permission before recording in any room.** Everyone present must
   agree.
2. **Write a simple consent form.** It should say: what we are recording,
   what it will be used for (academic research), that faces will be blurred,
   and that they can ask us to delete their data.
3. **Blur faces in every reference photo** before the data leaves the
   recording computer.
4. **Ask your supervisor about ethics approval.** Many venues require it for
   human-subject data. Start this early — approval can take weeks.
5. The echo recordings are only 60 milliseconds long and are stored as
   spectrograms, so speech cannot be recovered from them. Say this in the
   paper — it is a genuine privacy strength.

### E6. Turn recordings into training data

Once you have the recordings and matched photos, they need to be converted
into the format the training code reads. The model expects each sample to
contain:

| Field | Shape | Meaning |
|---|---|---|
| `thermal` | (1, 24, 32) | Thermal reading, scaled to 0–1 |
| `echo` | (2, 64, 64) | Two echo spectrograms |
| `sonar` | (10,) | Two ranges, two valid flags, four history slots |
| `mask` | (3,) | Which sensors were present |
| `gray` | (1, 192, 256) | The correct grayscale image, from the photo |
| `ab` | (2, 192, 256) | The correct colour, from the photo |
| `inv_depth` | (1, 192, 256) | Depth — we have none, so zeros |
| `depth_valid` | (1, 192, 256) | Zeros, since we have no depth truth |

Look at `scripts/prepare_llvip.py` in the repository — it does exactly this
conversion for a public dataset. Copy it to `scripts/prepare_capture.py` and
change the input part to read your `.npz` files and matched photos instead.

> We have **no depth ground truth** from a phone camera, so `depth_valid` is
> all zeros for our real capture. The model handles this — the depth loss is
> masked, so it simply skips depth for these samples. Mention this in the
> paper as a limitation.

---

## Part F — Experiments and measurements

These experiments turn the paper's *estimated* numbers into *measured* ones.
This is real scientific contribution.

### F1. Measure the actual power draw

**What the paper currently claims (estimated):** 36.5 mA total, 3.3 hours of
battery life.

**How to measure it properly:**

1. Set your multimeter to measure **current** (the mA setting)
2. Break the power connection between the battery and the board
3. Connect the multimeter **in series** — so all the current flows through
   the meter
4. Turn the node on and let it run normally
5. Record the reading

**Measure these five cases separately:**

| What to measure | How |
|---|---|
| Everything running | Normal firmware |
| Thermal only | Comment out the echo and sonar sections in `loop()` |
| Ultrasonic only | Comment out thermal and echo |
| Microphone + chirp only | Comment out thermal and sonar |
| Idle (Bluetooth connected, no sensors) | Comment out all three |

Fill in this table — it replaces Table I in the paper:

| Consumer | Estimated (mA) | **Measured (mA)** |
|---|---|---|
| Thermal array | 23.0 | ____ |
| MCU + Bluetooth | 8.0 | ____ |
| Ultrasonic ×2 | 3.0 | ____ |
| Microphone | 1.5 | ____ |
| Chirp emitter | 1.0 | ____ |
| **Total** | **36.5** | **____** |

**Also measure real battery life:** charge the battery fully, run the node
continuously, and record how long until it stops. Compare with the predicted
3.3 hours. **Report the real number, whatever it is.** If it is 2 hours, we
write 2 hours. An honest smaller number is far better than an unverified
larger one.

### F2. Validate the operating range

**What the paper currently claims (calculated from physics):** the system
works from about 5 to 8 metres.

**How to test it:**

Use a measuring tape. Place a person at known distances and record what each
sensor reports.

| Distance | Thermal: person visible? | How many pixels wide? | Ultrasonic reading | Echo peak visible? |
|---|---|---|---|---|
| 1 m | | | | |
| 2 m | | | | |
| 3 m | | | | |
| 4 m | | | | |
| 5 m | | | | |
| 6 m | | | | |
| 8 m | | | | |
| 10 m | | | | |

**What we predicted:**
- Thermal: a person should span about 4 pixels at 5 m, 2 pixels at 8 m
- Ultrasonic: should stop working past about 4 m
- Echo: should still work out to 8–10 m

**Then compare.** If the real numbers differ from the prediction, that is a
result, not a failure — it means the paper's Figure 4 gets replaced with
real measured data, which is much stronger.

### F3. Measure end-to-end latency

How long from the sensor reading to the picture appearing on screen?

The frame header already carries a timestamp from the node. On the host,
compare that timestamp to the current time when the image is displayed.
Record the average over several hundred frames.

### F4. Measure Bluetooth throughput

Count how many frames arrive per second on the host and multiply by frame
size. Compare against the paper's claim of "under 120 kbit/s".

---

## Part G — Command cheat sheet

**Every command below assumes you are inside the `novis_model` folder with
the virtual environment active** (your prompt shows `(.venv)`).

### Activate the environment (do this in every new terminal)

```bash
.venv\Scripts\activate
```

### Check everything works

```bash
python tests/test_smoke.py
```

```bash
python tests/test_host_pipeline.py
```

### Run without hardware

```bash
python -m host.live_infer --source synthetic --config configs/base.yaml
```

### Run with the real node

```bash
python -m host.live_infer --source ble --config configs/base.yaml
```

### Open the browser interface

```bash
python run.py
```

### Record real data

```bash
python record_capture.py --scene office_1 --minutes 5
```

### Prepare a public dataset (for whoever handles training)

```bash
python scripts/prepare_llvip.py --root data/raw/LLVIP --out data/processed/llvip
```

### Train (needs a GPU — this is the training teammate's job)

```bash
python train.py --config configs/thermal_llvip.yaml --data shards --train-shards data/processed/llvip/train --val-shards data/processed/llvip/val
```

### Evaluate

```bash
python eval.py --config configs/base.yaml --ckpt checkpoints/base/best.pt --data synthetic
```

---

## 10. Troubleshooting

### The board does not appear as a serial port

Double-tap the reset button quickly. A USB drive should appear. Then try
uploading again. Also check your USB cable actually carries data — many
cheap cables only charge.

### "MLX90640 not found"

- SDA and SCL swapped — try switching them
- Sensor connected to 5 V instead of 3.3 V
- Missing pull-up resistors — add 4.7 kΩ from SDA to 3.3 V and SCL to 3.3 V

### Ultrasonic always reads 0

- Check the sensor has 5 V, not 3.3 V (see Part B3 for the battery issue)
- Check the voltage divider is wired correctly — the **middle point** goes
  to the board, not the end of a resistor
- Make sure nothing is closer than 2 cm (the sensor's minimum distance)

### Ultrasonic readings jump around randomly

Increase the delay between reading the left and right sensor. They are
hearing each other.

### Microphone always reads 0

- `L/R` pin must be connected to GND
- Try changing `SWIDTH` from `24Bit` to `16Bit`
- Check SD, WS, and SCK are on the right pins

### Cannot hear the chirp

It is only 5 milliseconds long — very short. Temporarily change
`delayMicroseconds(250)` to `delay(50)` to make an obvious sound for
testing, then change it back.

### The host cannot find `NOVIS-Node`

- Is the node powered on?
- Is Bluetooth on and enabled for the terminal application?
- Try scanning with a phone app like nRF Connect first, to confirm the node
  is actually advertising
- On Windows, some Bluetooth adapters need the device to be un-paired first

### Frames arrive but decryption fails

The node's key and the host's key must match. Both currently use the
all-zero placeholder. Check neither side was changed.

### Bluetooth is too slow / frames are dropped

Reduce the thermal rate in `novis_node.ino` — change `>= 125` (8 Hz) to
`>= 250` (4 Hz) and see if it stabilises. Note this change in your log; it
affects the paper's throughput numbers.

---

## 11. Who does what

| Track | Owner | What it covers |
|---|---|---|
| **Hardware & firmware** | Hardware lead | Parts B, C — assemble the node, write the drivers |
| **Host & data capture** | Hardware lead | Parts D, E — receive data, record 12 scenes |
| **Measurements** | Hardware lead | Part F — power, range, latency |
| **Model training** | Training lead | Dataset download, prepare scripts, Stages A–C on the GPU |
| **Paper writing** | Everyone | Methods and Related Work now; Results after training |

### Suggested order of work

1. ✅ Buy all hardware — **done**
2. Set up the software (Part A) — can be done today, no hardware needed
3. Set up Arduino IDE (Part A3) — also today
4. Thermal sensor test (Part B2) — **start here now that it has arrived**
5. Ultrasonic test (Part B3)
6. Microphone test (Part B4)
7. Speaker test (Part B5)
8. Full assembly (Part B6)
9. Write the firmware (Part C)
10. Connect host to node (Part D)
11. Measure power and range (Part F) — these become paper numbers
12. Record the 12 scenes (Part E) — needs ethics approval first, so start
    that paperwork now
13. Hand the recorded data to the training lead for the final fine-tuning
    stage

### Keep a lab notebook

Write down, every time you work:
- What you wired, and to which pins
- What worked and what did not
- Every number you measured

You will need all of this when writing the paper's hardware section, and you
will not remember it three months from now.

---

## One last thing

When you get stuck, remember the rule from the start of this guide:
**add one thing at a time, and test after each one.** Almost every hardware
problem is solved by going back to the last state that worked and moving
forward more slowly.

Good luck.
