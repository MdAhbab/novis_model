# NOVIS — Data Collection to Model Training: the full plan

> ## ⚠️ SUPERSEDED FOR CAPTURE DAYS — read `session1_baa_capture.md` instead
>
> **24 Sept 2026.** BAB has a dead pixel and flashing the fix needs a PC we do
> not have, so we are not waiting. **Decision D2 has flipped: the capture
> sensor is BAA, and every photo is framed to BAA's view.** BAB stays wired and
> still records into every sample, but nothing is framed to it and no decision
> is made from it.
>
> **[`session1_baa_capture.md`](session1_baa_capture.md) is the capture-day
> document now.** This file is still correct — and still the reference — for
> scene variety (§8), session planning (§7, §9), ethics (§10), the shard
> pipeline (§12, §13), training (§14) and the paper (§15). Where the two
> disagree about **which sensor the photo is framed to**, the session document
> wins.
>
> What the flip buys: the model's thermal input stays **1 channel**, so the
> §14.5 model-side work is no longer a blocker, and `prepare_novis.py` needs
> no new flags — its default is already BAA-only.

**Updated 22 Sept 2026** — the design is **decided and locked in §0.5**:
two thermal sensors mounted co-axially, every ground-truth photo framed to one
of them, both frames recorded, and distance bucketed against measured ranges.
Read §0.5 before anything else, **with the banner above applied to D2/D3** —
the rest of the document is downstream of those six decisions.

Follow this document from the top on capture day. It
covers everything from "the module is built" to "the model is training on our
own real data", in plain language.

Companion documents:
`hardware_log.md` (how the node was built and debugged),
`NOVIS_Final_Module_Build.md` (assembly and pass criteria),
`NOVIS_Build_Guide.md` Part E (the original capture plan and the ethics rules).

---

## Which document to follow on a capture day

The hardware is built and passing, so most of the project's documents are
history now, not instructions. On a collection day:

| Document | Use it for | When |
|---|---|---|
| **`session1_baa_capture.md`** | **Everything you actually do in the room: setup, zoom lock, R_A, the scene loop** | **The whole day — start here** |
| **This one** | Scene variety (§8), how many (§7, §9), after-session steps (§11) | When planning, and afterwards |
| `NOVIS_Final_Module_Build.md` §6 | The pass criteria for one misbehaving sensor, and which bench sketch re-tests it | Only if a sensor looks wrong |
| `NOVIS_Final_Module_Build.md` §7, §10 | Battery wiring; the symptom → cause troubleshooting table | Only if something fails |
| `hardware_log.md` §4, §6-8 | The deep "why" behind a specific sensor's fix (`PS` to GND, `SD` to VIN, L/R to GND) | Only if §10 above did not solve it |
| `NOVIS_Build_Guide.md` Part E5 | The consent-form wording and the ethics rules | Before any scene with a person |

**Not needed on a capture day** — `NOVIS_Build_Guide.md` Parts A, B, C, D, F
(toolchain setup, sensor-by-sensor bring-up, firmware writing, host BLE,
power/range experiments), and the repository `README.md` (training). Sections
12-14 of this document are for the laptop afterwards, not for the room.

> **The `.json` is the dataset. The `.csv` is not.**
> "Download summary .csv" gives one row per sample with the sonar ranges, the
> echo peak numbers, and the thermal min/max/centre — a human-readable check
> that things looked sane. It contains **no thermal frame, no echo waveform,
> and no photo**, and `prepare_novis.py` cannot read it. Take the CSV if you
> like, but a session that ends with only CSVs has no training data in it at
> all, and the rooms have already changed by then.

---

## Contents

| # | Section | Read it when |
|---|---|---|
| 0 | [The whole plan on one page](#0-the-whole-plan-on-one-page) | First |
| 0.5 | [The design, decided](#05-the-design-decided) | **First — the six locked decisions everything else follows from** |
| 1 | [What the model needs, and why photos matter](#1-what-the-model-needs-and-why-photos-matter) | First |
| 2 | [Pre-flight: the night before](#2-pre-flight-the-night-before) | The night before |
| 3 | [The ESP32 side — what changed](#3-the-esp32-side--what-changed-and-how-capture-now-works) | Before flashing |
| 4 | [The ground-truth photo — the rules](#4-the-ground-truth-photo--the-most-important-30-minutes-of-the-project) | Before the first scene, once |
| 5 | [A scene, and how to name it](#5-a-scene-and-how-to-name-it) | Before the first scene |
| 6 | [The capture loop, step by step](#6-the-capture-loop-step-by-step) | Every scene |
| 7 | [How many? The numbers](#7-how-many-the-numbers) | When planning sessions |
| 8 | [Variety: what to change between scenes](#8-variety-what-to-change-between-scenes) | When planning sessions |
| 9 | [Session plan](#9-session-plan-tomorrow-and-after) | Tomorrow morning |
| 10 | [Ethics and consent](#10-ethics-and-consent) | Before any scene with a person |
| 11 | [After each session](#11-after-each-session-do-not-skip-this) | End of every session |
| 12 | [From .json to training shards](#12-from-json-to-training-shards) | After the first session |
| 13 | [Check the shards before training](#13-check-the-shards-before-training) | After step 12 |
| 14 | [Training](#14-training) | When the data is in |
| 15 | [What to report in the paper](#15-what-to-report-in-the-paper) | Writing up |
| 16 | [Mistakes that cost a whole session](#16-mistakes-that-cost-a-whole-session) | Keep open |
| 17 | [Printable session checklist](#17-printable-session-checklist) | On the phone, on the day |

---

## 0. The whole plan on one page

```
  ONCE, session 1 only
  ---------------------
  mount BAA + BAB co-axial  ->  measure both FOVs  ->  lock phone zoom to BAB
                            ->  measure R_A and R_B   (all of it into hardware_log.md)

  EVERY SCENE  (~90 s)
  ---------------------
  [ module + phone ]            one scene = one module position
        |                        |
        |  1. type scene id      |  2. photograph from the module's viewpoint,
        |     + distance in m    |     framed to BAB (the ground truth)
        |                        |  3. frame check: photo vs BAB's live pane,
        |                        |     side by side - same framing?
        |                        |  4. press "Capture a scene (25)"
        |                        |  5. stand still 25 s, move on
        v
  browser dashboard  ->  novis_dataset_<date>.json   (download every ~10 scenes)
        |                 every sample carries BOTH thermal frames
        v
  data/real_capture/*.json
        |
        |  python scripts/prepare_novis.py --baa-max-range R_A --r-use R_B
        v
  data/processed/novis/{train,val,stress}/shard_*.npz
        |
        |  python scripts/check_novis_shards.py     <- dead channels + split leaks
        v
  python train.py --config configs/fusion_full.yaml --init-from <pretrained>
        |
        v
  eval.py -> results/metrics.json + results/samples/eval_grid.png
             (report train/val AND stress separately)

  IN PARALLEL, on the laptop - never blocks a capture session
  ------------------------------------------------------------
  torch env + LLVIP download  ->  Stage A pretraining
                              ->  the 2-channel thermal change (14.5)
```

Everything below is the detail. Read §0.5 next — it is the set of decisions
the rest of this document is downstream of.

---

## 0.5 The design, decided

Everything below follows from six decisions. They are settled — this section
exists so nobody re-opens them mid-session. The reasoning is kept short; the
detail is in the sections referenced.

### D1 — Both thermal sensors, mounted co-axially

BAA (wide FOV, short usable range) and BAB (narrow FOV, long usable range) are
both wired, on separate I2C buses (§4.2c). Mount them **side by side, touching,
at the same height, both dead level, both pointing straight ahead** — so BAB's
view is a centred subset of BAA's.

*Not stereo.* Two 32x24 thermal sensors a few centimetres apart cannot produce
usable depth from disparity — it would be far below one pixel at any distance
that matters. The pair is a wide-plus-telephoto pair, like a phone's two rear
cameras, not a pair of eyes. The few centimetres of offset between them is
ignored everywhere and that is fine.

### D2 — The target frame is one sensor's view, always

> **REVISED 24 Sept 2026 — that sensor is now BAA, not BAB.** The rule below is
> unchanged in shape and in reasoning; only the name swaps. Read "BAB" as "BAA"
> and "BAA" as "BAB" throughout this subsection, and note the two consequences
> at the end. Procedure: `session1_baa_capture.md` step 2.
>
> **Why it flipped:** BAB has a dead pixel, the display fix needs a PC to flash,
> and waiting costs more than the narrower field is worth. BAA is wide
> (~110°×75°), works today, and caps the dataset at R_A ≈ 2.5–3 m instead of
> R_B ≈ 8 m. Shorter reach, but every scene in it is fully supported by the
> sensors — which was the point of the rule in the first place.
>
> **Two consequences of the flip:**
> - **The photo is now framed to the WIDER sensor.** The old version had the
>   photo inside BAA's wider view with margin to spare. Now the photo matches
>   BAA's own edges, so there is no margin — framing has to be right, which is
>   why the hot-mug edge test exists. If your phone cannot go wide enough, shoot
>   narrower deliberately and write it down: thermal wider than the photo is the
>   safe direction, the reverse is not.
> - **Scenes must be planned against R_A, not R_B.** A room deeper than R_A is
>   several scenes from several positions, never one scene from the doorway.

**Every ground-truth photo is framed to BAB's field of view.** Not BAA's, not
"whatever the scene needs" — BAB's, every scene, near and far alike.

This is the decision that makes the rest simple:

- Every target image in the dataset covers the **same angular extent**. No
  regime switching, no per-scene reasoning, nothing to get wrong at 4 pm on
  the fourth session.
- The rule "the photo is never wider than the sensing that supports it"
  (§4.1) holds at *every* distance, because BAB reaches the full depth of the
  main set and covers the whole target frame. BAA covers it too, as the middle
  of its wider view.
- BAA stops being "the sensor" and becomes **peripheral context** — extra
  input the model may use, never something it is asked to draw.

The cost is that reconstructions cover BAB's narrower field rather than BAA's
full 110°. That is an acceptable, ordinary camera-like field, and it is the
price of never training the model to invent unsupported detail — which was the
whole problem.

The dashboard's frame-check pane therefore shows **BAB**, and the photo is
lined up against that.

*(As of 24 Sept 2026 the pane shows **BAA** — see the revision note above.)*

### D3 — Two thermal channels into the model, fused by learning, not by hand

> **DEFERRED 24 Sept 2026 — not needed to start, and no longer blocking.** With
> BAA as the capture sensor, the model's thermal input stays **1 channel**,
> which the existing `ThermalStem` already takes. Nothing in §14.5 has to be
> written before training on real data.
>
> This is deferred, not cancelled. The dashboard still records **both** arrays
> on every sample (D6), so the two-channel version below stays available later
> as a clean ablation on the very same capture files — which is a better paper
> result than having only ever built one of them.

```
  thermal:  (1, 24, 32)   ->   (2, 24, 32)
                               channel 0 = BAA raw  (wide context)
                               channel 1 = BAB raw  (the target extent)
```

Both arrays go in raw. **No geometric reprojection, no stitching, no mosaic.**
At 24x32 the calibration effort that pixel-accurate registration would need
buys almost nothing, and the physical relationship between the two sensors is
identical in every single sample, so the first convolution learns it from the
data. `EchoStem` in this repo already takes 2 channels for exactly this kind of
reason; `ThermalStem` gains the same treatment.

Model-side cost, measured, not guessed: `src/novis/models/stems.py` has
**one** line to change — `nn.Conv2d(1, self.skip_ch, ...)` becomes a parameter.

### D4 — Pretraining synthesises the second channel by cropping

LLVIP/FLIR give one thermal image per scene, not a wide/narrow pair. So for
Stage A, the second channel is **made from the same image**:

```
  one public thermal image
        |                                  |
   whole image                        centre crop at the measured
        |                             BAA:BAB FOV ratio
   degrade_thermal()                  degrade_thermal()
        |                                  |
   channel 0 (BAA-like)               channel 1 (BAB-like)
```

Same `degradation.py` function, called twice. Nothing new to invent, and the
synthetic pair has the same geometry as the real one.

### D5 — Distance is bucketed against two measured numbers

Measure both sensors' usable range once (§4.2b, §4.2c):

| | symbol | expect | used for |
|---|---|---|---|
| BAA's usable range | **R_A** | ~2.5-3 m | the near/mid boundary; `--baa-max-range` in 1-channel fallback mode |
| BAB's usable range | **R_B** | ~6-8 m | the edge of the main set; `--r-use` |

Scenes past R_B go to the `stress` split, evaluated separately as graceful
degradation (§12, §14.3). They are collected, not skipped.

### D6 — Collection is architecture-agnostic, so collect now

The dashboard stores **both** thermal arrays on every sample regardless of any
of the above. So:

> Nothing in D3 or D4 has to be finished before capture day. The
> one-channel-vs-two-channel question is a **flag on `prepare_novis.py`, run
> against the same recorded files** — an ablation for the paper, never a reason
> to re-record a room.

What genuinely cannot be fixed afterwards, and so must be right from scene one:
**the mounting (D1), the photo framing (D2), the calibration numbers (D5), and
the per-scene distance you type in.** Those four. Everything else is
recoverable on the laptop.

### What this means for the two tracks

| Track | Blocked by | Start |
|---|---|---|
| **Capture** — sessions, scenes, photos | nothing | now (§2, §9) |
| **Model** — 2-channel stem, crop-based pretraining, Stage A | torch install, LLVIP download | now, in parallel (§2, §14) |

They do not wait on each other. That is deliberate: Stage A takes hours of GPU
time and the environment is not set up yet (§14.1), so if it is left until the
captures are done, that is weeks lost for nothing.

---

## 1. What the model needs, and why photos matter

NOVISNet is **supervised**. It learns one mapping:

```
  what the sensors saw          ->        what the room really looked like
  (thermal + sonar + echo)                (an ordinary photo)
```

So every training example is a **pair**. The sensor half comes from the ESP32.
The photo half has to come from a camera — and without it, the sample cannot
be trained on at all. This is the single most important thing to get right,
because a sensor reading with no matching photo is unusable, and there is no
way to add the photo back later.

One training example, in the model's own terms
(`src/novis/data/dataset.py`):

| Field | Shape | Where it comes from |
|---|---|---|
| `thermal` | 1 x 24 x 32 | MLX90640, 768 pixels |
| `echo` | 2 x 64 x 64 | INMP441 chirp recording, turned into a spectrogram |
| `sonar` | 10 | two HC-SR04 ranges + valid flags + history slots |
| `mask` | 3 | which modalities are present — all three, for this dataset |
| `gray` | 1 x 192 x 256 | **from the photo** — brightness the model must predict |
| `ab` | 2 x 192 x 256 | **from the photo** — colour the model must predict |
| `inv_depth`, `depth_valid` | 1 x 192 x 256 | zeros; the node has no depth sensor, so depth is left unsupervised |

This is the only NOVIS corpus where all three modalities are **real hardware
readings** rather than public images pushed through the simulated-sensor
functions in `degradation.py`. That is what makes it worth collecting, and
what the paper's real-hardware results rest on.

### A realistic expectation, stated now

The sensors measure heat, distance, and echo shape. **None of them measure
colour or texture.** The model can only guess colour from learned priors
("walls are usually pale", "a warm human-shaped blob has skin tones"). Judge
the results on structure — where the walls, furniture, and people are — and
treat plausible colour as a bonus, not as the headline claim. Say exactly
this in the paper too; it is a strength to be honest about it, not a weakness.

---

## 2. Pre-flight: the night before

Do these **before** capture day, not on the bench with everyone waiting.

### Hardware

- [ ] Module assembled and passing `NOVIS_Final_Module_Build.md` Section 6, on
      **battery**, not just USB
- [ ] LiPo charged; a second charged cell if you have one
- [ ] Something to stand the module on at a fixed height — tripod, stack of
      books, a small box. **Consistent height matters more than a particular
      height.** Chest height (~1.2 m) is a good default. Mark the height on
      the tripod leg with tape so it is the same next session.
- [ ] Tape measure
- [ ] A rigid way to hold the phone in the module's place (see Section 4)

### Firmware

Flash the dashboard from a laptop with USB, before you go anywhere:

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/dashboard
```

```bash
arduino-cli upload -p COM8 --fqbn esp32:esp32:esp32 firmware/dashboard
```

(Swap `COM8` for what `arduino-cli board list` shows. Hold **BOOT** if the
upload sticks at "Connecting...".) The compile has been verified against
`esp32:esp32:esp32` — if it fails on your machine it is the toolchain or a
missing library, not the sketch.

Then unplug USB, power from the battery, join the WiFi network **`NOVIS-B6`**
(password `novis1234`), and open **`http://192.168.4.1/`**.

- [ ] Thermal BAA panel says **sensor OK**; Thermal BAB panel too, if wired
- [ ] Sonar shows sensible numbers against a wall a known distance away
- [ ] Echo badge says **echo return detected** most seconds

If any of those three is wrong, fix it tonight. A session recorded with a dead
channel is a session thrown away.

### Phone

- [ ] Enough free storage and battery
- [ ] Camera set the way Section 4 tells you, and **locked there**
- [ ] The browser tab is going to hold the data — turn off anything that kills
      background tabs, and do not use a private/incognito tab

### Training PC (a separate track, but check it now)

Right now this repository has **no `.venv`, no prepared datasets, and no
checkpoints** — the model side has not been set up on this machine yet, and a
plain `import torch` currently fails. That does not block tomorrow's capture,
but it does block Section 14, so start it in parallel:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
python tests/test_smoke.py
```

Expected: `ALL SMOKE TESTS PASSED`. See the repository README for what to do
when `torch.cuda.is_available()` comes back False.

---

## 3. The ESP32 side — what changed, and how capture now works

`firmware/dashboard/dashboard.ino` is the sketch used for collection. The
sensor side is unchanged from the B6 test that passed: sensors are read once
per second, all in one pass, and the browser is served one consistent snapshot
per reading. What changed is the **capture behaviour in the page**, so the
exported file needs no cleaning afterwards.

**Two thermal sensors now.** BAA (wide FOV, shorter range) and BAB (narrower
FOV, longer range) are both read every cycle, on separate I2C buses (they
share a fixed address and would collide on one), and both are shown live and
stored on every sample — see Section 4.2c before your first session with BAB
wired in. Every sample from before BAB existed still loads fine; the second
array is additive, nothing about BAA's data or the model's input shape
changed.

**Re-flash before capture day** — these rules only exist in the new build.

| Rule the page now enforces | Why it exists |
|---|---|
| **One sample per new sensor frame.** The same reading is never stored twice, no matter how fast you press the button. | Previously, pressing "Capture" five times in one second stored five identical rows. Identical rows are not extra data; they just teach the model that one exact frame matters five times as much. |
| **Capture is refused while thermal reads NOT FOUND**, and the burst stops with a red message. | `prepare_novis.py` drops those samples anyway. Better to find out while you are still standing in the room. |
| **Capture is refused on a stale frame** (the node stopped refreshing for more than 2.5 s). | A frozen reading paired with a fresh photo is a wrong pair. |
| **"Capture a scene (25)"** takes exactly 25 samples, one per second, then stops by itself and says "scene done". | One button per scene. No counting, no forgetting to switch auto-capture off, no scene with 4 samples and another with 70. |
| **Scene notes** — room, distance to the main surface, people in view, lighting, free-text note — stored with the scene. | The paper needs a dataset table. Write it into the file at capture time, not from memory three weeks later. |
| **Per-scene quality pills** — "echo returns: 22/25", "sonar valid: 25/25". | Tells you the echo or the sonar was dead **for this scene**, while re-shooting still costs 90 seconds. |
| **Unsaved counter + a browser warning** before you close or reload the tab. | Samples live only in the tab. This is the one mistake that loses a whole session. |
| **Side-by-side frame check** — once a photo is attached, the photo and the live thermal frame appear next to each other, same size, same 4:3 crop, same guide lines. | Framing is the one error that cannot be repaired later, and it is invisible until you put the two pictures next to each other. See Section 4.4. |
| **Distance from the echo**, shown as `d = v x t / 2`, next to the distance the sonar reports for the same surface. | The echo channel used to be judged only by "did the peak jump". A distance in millimetres that can be checked against sonar and a tape measure is what makes echolocation a claim rather than a hope. See Section 4.5. |

Everything else is as before: `Capture 1 sample` for a single reading,
`Auto-capture` for a free-running capture you stop yourself, and
`Download dataset .json` / `Download summary .csv`.

**One sample per second is by design.** The sensor loop reads the thermal
frame, fires both sonars, emits the chirp and records the 60 ms echo window,
all once per second. That known-good timing is what passed the B6 battery
test, so it has been left alone; 25 samples therefore take about 25 seconds.

---

## 4. The ground-truth photo — the most important 30 minutes of the project

> ### ⚠️ Use [`session1_baa_capture.md`](session1_baa_capture.md) step 2 instead
>
> As of 24 Sept 2026 photos are framed to **BAA**, not BAB (D2, revised). The
> session document has the current procedure — the hot-mug wall test, which
> works even while BAB's panel is washed out. The rest of §4 below (why the
> rule exists, the photo procedure, the frame-check pane) is still correct with
> "BAB" read as "BAA".

Everything the model is scored on comes from these photos. Spend half an hour
getting the procedure right **once**, then never change it.

### 4.1 The one rule

> **Frame every photo to BAB's field of view — the narrow sensor — at every
> distance, near and far alike.** (Decision D2, §0.5.)
>
> **Revised 24 Sept 2026: frame to BAA, the wide sensor.** The principle below
> is what matters and is unchanged; only which sensor it names has swapped.

The general principle behind it: a photo must never be *wider* than the
sensing that supports it. If it is narrower, the model just gets extra context
in its input — harmless. If it is wider, you are asking the model to draw part
of a room its sensors never observed. It cannot, so it invents, and it learns
to invent everywhere.

Framing to BAB satisfies that principle at every distance in one stroke,
because BAB is the sensor that still resolves detail out at the far end of the
main set. Framing to BAA instead would satisfy it only up close — past R_A the
periphery of a wide photo has nothing behind it.

So: **lock the phone's zoom to match BAB once (§4.2), and never touch it
again.** The frame-check pane (§4.4) shows BAB for exactly this reason.

### 4.2 Measure both sensors' field of view, and lock the phone to BAB (once)

MLX90640 modules ship in a 55°x35° variant and a 110°x75° one — the repo's own
documents disagree about which is fitted, and now there is one of each anyway.
Settle both empirically, with mugs of hot water:

1. Put three warm mugs in a line about 2 m away: one straight ahead, one as far
   left as still shows in the heatmap, one as far right.
2. Nudge the outer two outward until they drop off the edge of the heatmap.
   That is that sensor's horizontal edge. Do it **once watching BAA's panel,
   once watching BAB's** — they will differ, that is the point of having both.
3. Check BAB is **centred inside BAA** (decision D1): a mug dead ahead should
   sit mid-frame in *both* panels. If BAB's centre is off to one side, the
   mounting is skewed — straighten it now, before any scene is recorded.
4. Stand the phone where the module is and photograph the same mugs. Adjust
   the phone's zoom until the photo's edges match **BAB's** edges — not BAA's
   (decision D2). Typically that means stepping up from 0.5x to 1x, or 1x to
   2x.
5. **Lock that zoom and never change it.** Write down the exact setting.

**Write all of it down in `hardware_log.md`**: BAA's FOV, BAB's FOV, the ratio
between them (Stage A's synthetic centre-crop uses it — decision D4), the phone
lens/zoom setting, and that BAB and the photo now match. The paper's
methodology section needs every one of these numbers, and so does session two.

### 4.2b Find out how far your sensors actually see (do this once too)

FOV (4.2) tells you the sensors' *angle*. It does not tell you their useful
*depth*. A doorway 6 m away can sit comfortably inside a 110° FOV and still be
almost invisible to the sensors: HC-SR04 hard-caps at 4 m, and MLX90640's
thermal contrast against a room fades out well before that. If the ground-truth
photo shows that doorway in full detail while the sensors carried almost
nothing about it, the model is being trained to hallucinate structure its
input never supported — everywhere, not just in that one scene.

So measure the usable range once, the same way you measured the angle:

1. Walk a warm object (a person is easiest) straight out from the module,
   stopping at 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0 m.
2. At each distance, look at the thermal heatmap and record whether the
   object is a **clearly distinct blob** — separable from the background, not
   just "technically warmer if you squint".
3. Also note the sonar reading and whether it tracks the tape measure.

```
distance | thermal: distinct blob? | sonar tracks? | notes
0.5 m    | yes                     | yes           |
1.0 m    | yes                     | yes           |
1.5 m    | yes                     | yes           |
2.0 m    | yes, fainter            | yes           |
2.5 m    | barely                  | yes           |
3.0 m    | no - blends into bg     | yes (sonar ok to 4 m even once thermal fades)
3.5 m    | no                      | marginal
4.0 m    | no                      | no (HC-SR04's hard limit)
```

Call the last distance where thermal was still a clear blob that sensor's
**usable range**. Run this procedure **twice** — once watching BAA's panel,
once watching BAB's — giving **R_A** and **R_B** (decision D5). R_A will
likely land well under HC-SR04's 4 m limit, and R_B well past it; that is
expected and fine, the sensors do not have to agree, which is exactly why
NOVIS fuses several of them. **Write both numbers in `hardware_log.md` next to
the FOV findings.** Section 8 and `scripts/prepare_novis.py` both use them.

This does not mean stop capturing scenes beyond R_B — see Section 8 and 12 for
what to do with them instead of throwing them away.

### 4.2c Two thermal sensors: BAA (wide/near) and BAB (narrow/far)

The module carries two MLX90640 units, wired on separate I2C buses so they
don't collide (they share a fixed address and cannot sit on one bus) —
`firmware/dashboard/dashboard.ino` reads both every cycle, and the dashboard
shows both live: **Thermal BAA** (wide FOV, shorter usable range) and
**Thermal BAB** (narrower FOV, longer usable range). They are complementary,
not redundant: BAA sees more of a near scene, BAB resolves a far one BAA
cannot.

**They are never merged into one image by hand** — no stitching, no mosaic,
no reprojection. Both raw arrays are stored on every sample (`thermal` = BAA,
`thermalFar` = BAB) and both are handed to the model as two channels, which
learns to combine them itself (decision D3, §0.5). The one-channel path —
picking a single sensor per scene by distance — is kept as the fallback
baseline and the ablation, selected by a flag at prepare time (§12). Either
way, **capture does not change**: both arrays are recorded regardless.

**Calibrate BAB the same way as BAA (Section 4.2b), separately**, and expect
a *longer* usable range, not the same one — this is the point of having two
units:

```
distance | BAA: distinct blob? | BAB: distinct blob? | notes
0.5 m    | yes                 | yes (or too close - some lenses have a MFD)
1.0 m    | yes                 | yes
2.0 m    | yes                 | yes
2.5 m    | fading              | yes
3.0 m    | no                  | yes
5.0 m    | no                  | yes
7.0 m    | no                  | fading
8.0 m    | no                  | no
```

Two numbers come out of this — **R_A** and **R_B** (decision D5) — and both go
in `hardware_log.md` next to the FOV findings:

- **R_A, BAA's usable range** (e.g. 2.5 m) — the near/mid boundary for
  planning scenes (§8), and `--baa-max-range` in the one-channel fallback.
- **R_B, BAB's usable range** (e.g. 7.5 m) — the edge of the main dataset, and
  `--r-use`. Past it neither sensor carries anything, so those scenes go to
  the stress split (§12).

**The frame-check pane shows BAB**, because BAB's view is what every photo is
framed to (D2). Line the photo up against that, at every distance. BAA's own
panel is still worth a glance for near scenes — it should show the same warm
objects, just with more room around them — but it is context, not the thing
being matched.

If BAB drops out mid-session (`NOT FOUND`), **stop and fix it rather than
carrying on.** BAB now defines the target frame, so without it you cannot
frame a photo correctly at all — this is different from the old one-sensor
setup where a far scene merely came out poor. Near scenes are not a safe
exception either: the framing still comes from BAB.

### 4.2d Dead pixels — normal, not a fault, and already handled

A single dot that stays in **exactly the same position** in every frame while
the rest of the picture moves is a **dead pixel**. It is not a wiring fault,
not a calibration error, and not a reason to replace the sensor.

- Melexis sells MLX90640 parts with a small number of dead or deviating
  pixels as a **documented part tolerance**. The factory even records the ones
  it knows about in the sensor's EEPROM.
- The Adafruit driver we use never repairs them: `getFrame()` calls
  `MLX90640_CalculateTo` but not `MLX90640_BadPixelsCorrection`. So they come
  through raw, every frame, forever.

**Calibration does not fix this.** Calibration corrects a pixel's gain and
offset — it assumes the pixel is *reading something*. A dead pixel reports
nothing to scale. There is no constant that repairs it, which is why the fix
is interpolation from its neighbours, not calibration.

**Do this once, then forget it:**

1. **Confirm it is really a dead pixel.** Wave a warm hand across the view. If
   the dot does not move while everything else does, it is dead. If the dot
   moves, jumps around, or comes and goes, it is *not* a dead pixel — suspect
   the I2C wiring, and check §3 before going on.
2. **Write down which sensor and roughly where** in `hardware_log.md`. That is
   all the bookkeeping this needs.
3. **Carry on capturing.** Nothing about the procedure changes.

**What the tools already do about it**

- **The dashboard** ranges its colours on the 1st–99th percentile rather than
  the literal min/max, so one bad pixel cannot wash the rest of the picture
  out into flat yellow, and the hotspot crosshair skips outlier pixels so it
  cannot land on the defect. The MIN/MAX readout still shows the *literal*
  extremes on purpose — that is what makes the pixel visible at all — so a
  `min` of `-0.0°C` next to a normal-looking picture is the expected
  appearance of a dead pixel, not a new problem. The status pill reads
  `sensor OK · check dead pixel` when it detects one.
- **`prepare_novis.py`** finds dead pixels automatically and fills them from
  their neighbours before writing any shard, per sensor, and prints what it
  found. It only flags a pixel that is off its neighbours in ≥90% of *all*
  frames in the run, so a real person at distance can never be mistaken for a
  defect and erased. `--dead-pixel-thresh 0` turns it off; the raw `.json`
  export is never modified either way.

So: one or two dots, fixed in place — note them and keep going. **More than
about ten**, or a whole patch, is a different problem (cracked lens, bad bus,
failing part) and `prepare_novis.py` will warn you about it.

### 4.3 The photo procedure, every scene

Two ways to get the photo in. Prefer the first — it lets you line up the shot
*before* you take it, instead of checking afterwards.

**"Open live camera" (preferred, one-time setup on the capture phone)**

This shows the phone's live camera feed right inside the same box as the
thermal view, with the same guide lines, so you frame the shot correctly the
first time. `firmware/dashboard/dashboard.ino`'s page is served over plain
`http://192.168.4.1/`, and phone browsers only grant camera access on a
"secure origin" (HTTPS, or localhost) — so **the first time**, on the phone
you'll use for capture:

1. In Chrome, go to `chrome://flags/#unsafely-treat-insecure-origin-as-secure`.
2. Enable it, and add `http://192.168.4.1` in the box that appears.
3. Relaunch Chrome.

This is a one-time setup per phone, and the protocol already calls for using
the same phone every session, so it only has to be done once. If it's skipped
or the browser still refuses, the dashboard shows a note with these same
steps and you fall back to the second method below.

1. **Type the scene id, then press "Open live camera".**
2. **Line it up.** The live feed and the live thermal frame are shown side by
   side, same size, same guide lines — see Section 4.4 for how to read them.
3. **Press "Capture this frame"** once it looks right. This crops to 4:3 and
   shrinks to 512x384, exactly like the fallback method, and stores it once
   for the whole scene.
4. **Then step out of the sensors' view** — unless a person in the scene is
   the point. You are the warmest thing in the room and the thermal sensor
   will see you.

**"Take / choose photo" (fallback, works everywhere)**

Opens the phone's normal camera app full-screen. No live thermal comparison
while shooting — you check the framing afterwards, in the side-by-side view
(Section 4.4), and re-shoot if it's off.

1. **Same viewpoint.** Hold the phone where the module is, pointing where the
   module points. The closest practical version: leave the module on its
   stand, hold the phone directly above or beside it (a few cm), lens facing
   the same way. If you can bracket the phone to the module rigidly, better —
   then it is identical every time.
2. **Same phone, same lens, same zoom, every session.** Changing lens mid-way
   silently splits your dataset into two incompatible halves.
3. **Turn off:** HDR (it changes brightness in a way the sensors cannot
   predict), portrait mode, beauty filters, flash, and any auto night mode
   you can disable. Ordinary photo mode only.
4. **Hold still, take one photo.** The dashboard crops it to 4:3 and shrinks
   it to 512x384 in the browser, and stores it once for the whole scene.
5. **Then step out of the sensors' view** — unless a person in the scene is
   the point. You are the warmest thing in the room and the thermal sensor
   will see you.

### 4.4 Check the framing before you capture — the side-by-side view

As soon as a photo is attached, the dashboard shows it **next to BAB's live
thermal frame**, at the same size, the same 4:3 crop, and with the same guide
lines (centre cross, plus thirds) drawn over both. BAB, not BAA — it is BAB's
view the photo is framed to (D2), so BAB is what the photo has to match. This
is the verification step: framing is the one mistake that cannot be repaired
afterwards, and it is almost invisible until the two pictures sit side by
side.

**How to use it, in ten seconds:**

1. Put something warm in the scene that you can also see in the photo — your
   hand, a person, a mug of tea, a radiator.
2. Look at which box of the grid it falls in on the **photo** side.
3. Look at which box it falls in on the **thermal** side.
4. Same box, roughly the same height? Good — capture. Drifting left in one and
   right in the other? The phone was not where the module is. Re-shoot the
   photo; it costs 20 seconds now and the whole scene later.

Match the **position** of the warm blobs, not their sharpness. The thermal
side is 32x24 pixels and will always look like a smear next to a phone photo;
that is expected and is exactly what the model has to work from. What you are
checking is *where* things are, not *how clearly* they appear.

If the two panes disagree consistently in the same direction across several
scenes, the phone mount is off, not the individual photos — fix the mount
before collecting more.

### 4.5 What the echo distance is for

The echolocation panel now reports an actual distance:

```
  d = v x t / 2        (the classic 2d = vt)
  v = 343 m/s
  t = time from the chirp to the first return above the noise floor
```

The chirp leaves the speaker, hits a surface, and comes back to the mic, so
the sound covers **twice** the distance to that surface — hence the divide by
two. The first ~6 ms of the recording are ignored, because the speaker sits
centimetres from the mic and its chirp reaches it directly through the air;
without that blanking window every scene would report a few centimetres.

Next to it the panel shows **what the sonar says** about the nearest surface,
and the gap between the two. This is worth watching while you collect:

| Agreement | What it means |
|---|---|
| within ~30 cm (green) | Echo and sonar independently agree. The echolocation path is genuinely working — this is the number the paper wants. |
| 30-70 cm | Plausible. They may be seeing different surfaces; the sonars point outward at an angle and the chirp is broad. |
| worse than 70 cm, repeatedly (red) | Look at it. A soft room may simply not return a clear echo, but a *consistent* disagreement suggests the mic, the amp, or the chirp is not doing its job. |

`no return` is a real reading, not a failure — some scenes genuinely have no
hard surface in range. It is stored as `0` and the raw waveform is kept, so
nothing is lost.

The number is written into every captured sample as `echoDistanceMm` (with
`echoTofMs`), and into the summary CSV, so echo-versus-sonar agreement can be
plotted straight from the dataset without re-deriving anything. The full echo
waveform is still stored alongside it, so a different detection rule can
always be tried later.

### 4.6 What good and bad pairs look like

| Good | Bad |
|---|---|
| Photo taken from the module's position | Photo taken from the doorway, or over your shoulder |
| Warm object in the same grid box on both sides of the frame check | Blob top-left on the thermal, bottom-right in the photo |
| Module and photo facing the same wall | Photo shows the whole room, sensors see one corner |
| Room unchanged for the full 25 s | Someone walks through halfway |
| Same lens and zoom as every other scene | 0.5x for indoor rooms, 1x for corridors |

---

## 5. A scene, and how to name it

A **scene** is one position of the module, pointing one direction, with the
room in one arrangement. Move the module, move the furniture, or let a person
walk in — that is a new scene, needing a new id and a new photo.

Within one scene the room does not change, so you take **one photo** and
capture **25 sensor samples** against it. Those 25 all share the same target
image. They are not wasted duplicates — each has different sensor noise, a
slightly different echo, and slightly different sonar returns, which teaches
the model to be robust to exactly the noise the real node produces. But they
are **not** 25 new scenes, and the dataset's real size is the number of
distinct scenes.

### Naming scheme

```
  <room>-<arrangement>-v<viewpoint>

  bedroom-01-v1        bedroom, arrangement 1, viewpoint 1
  bedroom-01-v2        same room and furniture, module moved or rotated
  bedroom-02-v1        bedroom, furniture moved / a person added
  kitchen-01-v3
  corridor-a-01-v1
```

Keep it consistent: `prepare_novis.py` splits train/val **by scene id**, so a
consistent scheme is what lets you hold out whole rooms later. Never reuse an
id for a different room — the two rooms would share one photo.

**The cheapest way to get more scenes:** from one module position, rotate it
15-30° and take a new photo. Same room, same trip, new viewpoint, new scene.
Four rotations from one spot is four scenes in about six minutes.

---

## 6. The capture loop, step by step

Per scene, this is about **90 seconds**.

1. **Place the module** where it will sit for the whole scene, at your
   standard height, pointing at what you want captured.
2. **Type a scene id** in the dashboard, step 1. Typing a new id clears the
   photo, so a scene can never silently inherit the previous scene's photo.
3. **Fill the scene notes** — room, distance to the main surface in metres
   (use the tape measure, or read it off the sonar panel), people in view,
   lighting. They are stored with the scene's first sample.
4. **Take the photo** — "Take / choose photo", following Section 4.3.
5. **Check the framing** in the side-by-side view that appears (Section 4.4).
   Warm object in the same grid box on both sides? Then continue. If not,
   re-shoot the photo now — this is the only moment it can be fixed.
6. **Step out of the sensors' view.**
7. **Press "Capture a scene (25)"** and stand still. The pill counts down and
   says "scene done - move the module" when it finishes.
8. **Glance at the two quality pills**, and at the echo-versus-sonar
   agreement (Section 4.5). If "echo returns" is under about half, "sonar
   valid" is low, or the echo distance disagrees with sonar by a metre every
   time, something is wrong with the hardware, not the room — stop and fix it
   before capturing more.
9. **Move on.** New position, new id, new photo.
10. **Download the .json every ~10 scenes**, and always before closing the tab.

If a scene goes wrong (someone walked through, the photo was blurry), just
capture the scene again under a new id — `-v2`, `-v3`. Do not try to delete
the bad one on the phone; note the bad id on paper and drop it later with
`--held-out-scenes` or by editing the .json.

---

## 7. How many? The numbers

Two different numbers get confused here, so keep them separate:

- **Samples per scene** — 25. This is a noise-robustness number, and it
  saturates fast.
- **Scenes** — this is the real size of the dataset, and it is what the
  results depend on.

### Samples per scene: 25 is the answer

| Per scene | Verdict |
|---|---|
| 10 | Too few. The sensor-noise variety the extra samples exist for barely shows up. |
| **20-25** | **Right.** ~25 s standing still, and the noise across them genuinely differs. This is what the dashboard's one-button capture does. |
| 30-40 | No measurable gain; the room is identical and so is the target photo. Costs you scenes instead. |
| 60+ | Actively unhelpful — it over-weights one photo in the loss. |

So: **25, and spend any extra time on more scenes instead.**

### Scenes: aim for 120

| Level | Scenes | Samples per scene | Total samples | Rooms | Sessions |
|---|---|---|---|---|---|
| Pilot — proves the pipeline, no claims | 10-15 | 25 | ~300 | 2 | tomorrow morning |
| Bare minimum for a thin result | 40 | 25 | ~1,000 | 4 | 2 |
| **Recommended target** | **120** | **25** | **~3,000** | **8** | **4** |
| Strong — comfortable ablations and a real test set | 250+ | 25 | ~6,000+ | 10+ | 8 |

Time: about 90 seconds per scene, so 30 scenes is roughly 45 minutes of actual
capture plus setup and moving between rooms — call it a 1.5 hour session.
**120 scenes is four such sessions.** That is very reachable.

Below about 30 scenes the validation numbers are too noisy to claim anything.
Past about 250 you are into diminishing returns unless you are adding
genuinely new room types.

### Plan the split before you collect, not after

- **Train** — most rooms
- **Validation** — 15-20% of scenes, used for choosing checkpoints
- **Test** — **2-3 rooms you never train on at all**, reserved for the final
  number in the paper

You cannot collect 120 scenes in one room and split it afterwards. Aim for at
least **6-8 physically different rooms**, and decide on day one which two will
be the test rooms — then capture them, and do not look at them again until
the very end.

---

## 8. Variety: what to change between scenes

Variety is worth more than volume. A thousand samples of one room teach the
model that room; three hundred samples across twenty rooms teach it the task.

Vary deliberately:

- **Rooms** — different sizes, shapes, and wall materials. Hard walls echo
  very differently from curtains and sofas, and that difference is exactly
  what the echo channel carries.
- **Distance, bucketed against your own measured R_A and R_B** (§4.2b, §4.2c)
  — not a generic "0.5-4 m". Target mix for the main set:

  | Bucket | Range | Share | What it is |
  |---|---|---|---|
  | **near** | up to R_A | ~40% | both sensors strong; the easy case |
  | **mid** | R_A to ~0.6 x R_B | ~35% | BAB carrying it, BAA fading to context |
  | **far** | ~0.6 x R_B to R_B | ~20% | the edge of what the module can do |
  | **stress** | beyond R_B | ~5% | collected on purpose, kept out of train/val |

  The stress bucket matters: "reconstruction degrades gracefully past the
  module's usable range" is a real, checkable claim, and
  `prepare_novis.py --r-use` routes those scenes out of train/val by itself
  (§12). Silently training on them instead would just teach the model to
  guess distant detail from nothing, everywhere.
- **Furniture arrangement** — move a chair, open a door, re-shoot.
- **People** — with and without, spread across near, mid and far. A person is
  the strongest thermal signal you will ever record, so a dataset with no
  people leaves the thermal channel badly underused. Aim for roughly **a
  third of scenes with a person in view** (consent first — Section 10).
- **Lighting** — the sensors do not care, but the *photo* does, and the model
  is being asked to predict that photo. **Keep the main set at ordinary,
  consistent indoor lighting.** If you want a "works in the dark" claim,
  collect a small separate batch: same room, same module position, same scene
  arrangement, lights on for one scene id and off for the next. That pair is
  the evidence; mixing lighting randomly through the whole set just makes the
  task noisier.

A workable per-room budget (15 scenes, ~25 minutes):

| Scenes | What |
|---|---|
| 4 | Empty room, four viewpoints (rotate the module), near/mid |
| 3 | Near: facing a wall or furniture well inside R_A |
| 3 | Far: out towards R_B |
| 1 | Beyond R_B — the stress bucket |
| 4 | With a person, spread across near / mid / far |

**BAB's narrower frame is a quiet bonus here**: a narrow field means one room
yields more distinct, non-overlapping viewpoints than a 110° field did, so 15
scenes per room is easier to reach than it was, not harder.

### A room bigger than R_B is not one scene — it is several

BAB buys real depth, but it is not unlimited. Do not point the module down a
12 m hall and call it one scene; past R_B you are photographing structure
nothing on the module can sense. Instead, **move the module through the
room**, taking ordinary near/mid/far scenes from each position — the naming
scheme already supports it (`lab-01-posA-v1`, `lab-01-posB-v1`, ...):

```
  12 m hall, R_B = 7.5 m, two module positions:

  entrance ----------|------------ 7.5 m ------------|
  posA: [module] -> forward; R_B reaches most of the way down

                   posB (moved ~6 m in): [module] -> the far end, now in range
```

Add 2-3 rotations at each position, same as any other room. Two positions x
three rotations is six honest scenes from one hall, instead of one scene that
half-teaches the model to invent the far wall.

Avoid, at least for the first sessions:

- Scenes where the module and the photo point in noticeably different
  directions
- Very reflective or very cluttered close-range setups — get the easy cases
  working before the hard ones
- Capturing a scene while someone walks through it. The photo is one instant;
  the samples take 25 seconds.

---

## 9. Session plan: tomorrow, and after

### Tomorrow — Session 1 (pilot first, then collect)

**Do not collect 120 scenes before checking the pipeline once.** The pilot
costs 45 minutes and protects everything after it.

Session 1 is mostly calibration. That is correct and worth the time — the four
things that cannot be fixed later (D6) are all settled here.

| Time | What |
|---|---|
| 0:00 | Power up on battery, join `NOVIS-B6`, open `192.168.4.1`. Confirm **both** thermal panels say sensor OK, sonar sensible, echo returning. |
| 0:10 | **Mounting check (D1)**: BAA and BAB side by side, same height, level, both forward. A mug dead ahead sits mid-frame in both panels. Straighten now if not. |
| 0:25 | **FOV measurement (§4.2)**: BAA's edges, BAB's edges, the ratio between them. Lock the phone zoom to BAB. Write all of it in `hardware_log.md`. |
| 0:50 | **Range measurement (§4.2b/4.2c)**: walk a warm body out in 0.5 m steps, get R_A and R_B. Write them down. |
| 1:15 | Capture **3 scenes** in one room, 25 samples each. Download the .json. |
| 1:25 | **Stop.** Go to the laptop, copy into `data/real_capture/`, run §12 and §13 on it. |
| 1:40 | Checker happy? Go back and collect the rest of the room budget (§8). Not happy? Fix it now — every later session inherits the fault. |
| ~3:00 | Download, back up, write session notes including R_A, R_B, FOVs, zoom setting. |

Target for the day: **1 room properly, 10-15 scenes**, with all five
calibration numbers written down. Sessions 2-4 are the volume; this one is the
foundation, and rushing it is the one way to lose all of them.

### Sessions 2-4

One or two new rooms each, 15 scenes per room, same procedure. Run
Sections 12-13 after **every** session, not at the end of the project.

Keep the two test rooms for one dedicated session, and label them clearly in
your notes so nobody accidentally trains on them.

---

## 10. Ethics and consent

This applies the moment a person appears in a photo. `hardware_log.md` flags
it as Part E and warns it takes weeks — **start the paperwork before you need
it, not after.**

- **Ethics approval** — ask your supervisor now. Many venues require it for
  human-subject data, and approval can take weeks.
- **Consent from everyone in the room, before recording.** A simple written
  form: what is recorded, what it is used for (academic research), that faces
  will be blurred, and that they can ask for their data to be deleted.
  Record that you obtained it.
- **Blur faces in every photo before the data leaves the recording machine** —
  not later, not "before publishing".
- Worth stating in the paper: the 60 ms echo recordings are stored as
  spectrograms and speech cannot be recovered from them. That is a genuine
  privacy strength — but it only holds if you store spectrograms, which
  `prepare_novis.py` does.
- The node's WiFi AP is open to anyone in radio range with the password. In a
  shared building, that is worth knowing during a capture session.

If consent is not in place yet, **collect the people-free scenes first**. There
are plenty (empty rooms, distances, arrangements) and none of them wait on
paperwork.

---

## 11. After each session — do not skip this

1. **Download the `.json`** before closing the tab. The page will warn you,
   but do not rely on the warning.
2. **Copy it into `data/real_capture/`** on the training PC, named by session
   date. `data/` is gitignored, so **back it up somewhere else as well** —
   these files cannot be re-recorded, the room has already changed.
3. **Optionally download the summary `.csv`** — a one-line-per-sample table
   that is easy to skim for something obviously wrong. It is a convenience
   only: it holds no thermal frame, no echo waveform and no photo, so it is
   **not** training data and `prepare_novis.py` ignores it. Never treat a
   downloaded CSV as "the session is saved".
4. **Write session notes**: which rooms, roughly how many scenes, anything
   that misbehaved, any scene id that should be dropped. That note is what
   `hardware_log.md` and the paper's methodology section need later.
5. **Run Sections 12 and 13 the same day.**

---

## 12. From .json to training shards

```bash
python scripts/prepare_novis.py --captures "data/real_capture/*.json" --out data/processed/novis
```

This reads every export, decodes each scene photo, converts each sample into
the exact arrays the model expects, and writes compressed `.npz` shards to
`data/processed/novis/train/` and `.../val/`.

It splits **by scene, never by sample** — samples from one scene are
near-duplicates, and splitting them randomly would put copies of the same
scene on both sides and produce a validation score that means nothing.

### Holding out your test rooms

```bash
python scripts/prepare_novis.py --captures "data/real_capture/*.json" ^
    --out data/processed/novis_test ^
    --held-out-scenes bedroom-03-v1,bedroom-03-v2,kitchen-01-v1
```

### Splitting off the beyond-range scenes: `--r-use`

```bash
python scripts/prepare_novis.py --captures "data/real_capture/*.json" ^
    --out data/processed/novis --r-use 2.5
```

Pass the number you measured in Section 4.2b. Every scene's "main surface
distance (m)" (already collected with every scene, Section 6 step 3) gets
bucketed **near / mid / far-valid / beyond**, printed as a summary. Scenes
beyond R_B go to `data/processed/novis/stress/` instead of train or val —
held out of both, not thrown away. Train Stage D on train/val as usual, then
evaluate the `stress/` shards **separately** (Section 14) and report both
numbers: reconstruction quality within the sensors' reach, and how it degrades
past it. That is the point of collecting those scenes at all — see Section 8.

Omit `--r-use` entirely and nothing changes from before; every scene goes to
train/val as it always did. Only pass it once you have an actual measured
number from Section 4.2b — a guessed one defeats the purpose.

### Using both thermal sensors

Decision D3 (§0.5) is **two channels**: BAA and BAB both go in, the model
learns the fusion. That needs the model-side change listed in §14.5; until
that lands, prepare the one-channel fallback so the pipeline stays runnable
end to end.

**Fallback / baseline — one channel, sensor chosen per scene:**

```bash
python scripts/prepare_novis.py --captures "data/real_capture/*.json" ^
    --out data/processed/novis_1ch --baa-max-range 2.5 --r-use 7.5
```

`--baa-max-range` is R_A — at or below it the `thermal` array is BAA's frame,
beyond it BAB's (falling back to BAA with a printed warning if BAB's frame was
missing for that sample). `--r-use` is R_B, the edge of the main set. Omit
`--baa-max-range` and every scene uses BAA, exactly as before BAB existed.

**Both runs read the same capture files.** One-channel versus two-channel is
an ablation to report, not a fork in the data — which is the whole reason the
dashboard records both arrays on every sample (D6).

### Dead pixels are repaired automatically

Every run prints one line per sensor before anything else:

```
BAA: no dead pixels detected in 1840 frames
BAB: 1 dead pixel(s) at (5,10) - repaired from neighbours in every frame
```

That is the normal, expected output for these parts (§4.2d) — nothing to act
on. The repair fills the pixel from its live neighbours before normalisation,
which matters most under `--thermal-norm perframe`, where one pixel reading
0 °C would otherwise set the low end of every frame it appears in.

Copy those lines into the session log (§11). If the count ever jumps, the
sensor changed, and you want to know which session that started in.

`--dead-pixel-thresh 0` disables the repair; `--dead-pixel-thresh`/
`--dead-pixel-frac` tune it. The raw `.json` exports are never modified.

### Thermal normalisation — a real choice, so make it deliberately

- `--thermal-norm fixed` (the default, with `--temp-min 15 --temp-max 40`)
  maps an absolute temperature window, so a person looks the same brightness
  in every scene and the numbers stay physically meaningful.
- `--thermal-norm perframe` rescales each frame to its own min/max. That is
  effectively what the 8-bit thermal cameras behind LLVIP do, and
  `prepare_llvip.py` feeds those images straight into `degrade_thermal`, so
  **perframe is the closer match to the pretraining distribution** — at the
  cost of amplifying sensor noise in a room with nothing warm in it.

Build both once; it costs minutes:

```bash
python scripts/prepare_novis.py --captures "data/real_capture/*.json" --out data/processed/novis_fixed --thermal-norm fixed
python scripts/prepare_novis.py --captures "data/real_capture/*.json" --out data/processed/novis_perframe --thermal-norm perframe
```

Fine-tune on each and report the difference. It is a cheap ablation and a real
paragraph in the paper.

---

## 13. Check the shards before training

```bash
python scripts/check_novis_shards.py data/processed/novis
```

This is a five-second read of the whole prepared set. It prints the shape and
range of every array, and it fails loudly on the things that make a training
run meaningless:

- an array with the wrong shape, wrong range, or NaNs
- **a dead input channel** — thermal frames that are nearly flat, an all-zero
  echo spectrogram, or more than half the samples with no valid sonar range
- **a scene that appears in both train and val** (it compares the target
  images directly, so it catches the case where one room was captured twice
  under two different ids)
- how many *distinct scenes* are actually behind your sample count — the
  number that matters, printed next to the number that flatters

Exit code is 1 when it finds a real problem, so it can sit in front of
training in a script. Run it after every session's prepare step.

You can also spot-check by hand:

```bash
python -c "import numpy as np; z=np.load('data/processed/novis/train/shard_0000.npz'); [print(k, z[k].shape, z[k].min(), z[k].max()) for k in z.files]"
```

`thermal` should be `(N,1,24,32)` in [0,1], `echo` `(N,2,64,64)`, `gray`
`(N,1,192,256)`, and `mask` all ones.

---

## 14. Training

### 14.1 The honest state of it

The training track has not been started on this machine: there is no `.venv`,
no `data/processed/`, and no `checkpoints/`. So the fine-tune command below
**cannot run yet** — it needs a pretrained checkpoint that does not exist.
Get the environment working (Section 2) and Stage A running while the capture
sessions happen; the two tracks are independent.

### 14.2 Why the real set is allowed to be small

It is not carrying the whole training load:

1. **Stage A / Stage B** — pretrain on public data (LLVIP, BatVision) run
   through the simulated-sensor functions in `degradation.py`. That is where
   the model learns what rooms look like, from tens of thousands of images.
2. **Stage D** — fine-tune and evaluate on *this* dataset, from the real node.

The real corpus's job is to close the simulation-to-reality gap and to give
honest numbers on real hardware — not to teach the model vision from scratch.
That is why a few thousand real samples is a sensible target rather than a
hundred thousand.

### 14.3 The path, in order

**Step 1 — Stage A (thermal pretraining).** Download LLVIP per
`data/raw/README.md`, then:

```bash
python scripts/prepare_llvip.py --root data/raw/LLVIP --out data/processed/llvip
python train.py --config configs/thermal_llvip.yaml --data shards --train-shards data/processed/llvip/train --val-shards data/processed/llvip/val
```

This is the one that matters most for our results, because thermal is the
channel that carries scene structure. Expect it to run for hours — start it
overnight and record the real wall-clock time; the paper needs the measured
number, not an estimate.

**Step 2 — Stage B (echo pretraining), optional if time is short.** BatVision,
per `data/raw/README.md` and `configs/echo_batvision.yaml`. One honest caveat
to note if you do it: `prepare_batvision.py` turns the *whole* recording into
a spectrogram, while our node records a 60 ms window after the chirp. If the
BatVision clips are much longer, the two echo distributions differ, and the
pretraining helps the echo channel less than it looks like it should. Trimming
the BatVision waveforms to the first 960 samples before
`D.wav_to_spec` would make them match; worth a line in the paper either way.

**Step 3 — Stage C (fusion).** Combine the prepared public shards and train
with `configs/fusion_full.yaml`, seeded from Stage A/B via `--init-from`.
This stage turns on the perceptual and adversarial terms.

**Step 4 — Stage D (this dataset).** Fine-tune on the real capture:

```bash
python train.py --config configs/fusion_full.yaml --data shards ^
    --train-shards data/processed/novis/train ^
    --val-shards   data/processed/novis/val ^
    --init-from checkpoints/fusion_full/best.pt ^
    --run-name novis_real
```

Then evaluate — on the **held-out test rooms**, not on val:

```bash
python eval.py --config configs/fusion_full.yaml --ckpt checkpoints/novis_real/best.pt ^
    --data shards --val-shards data/processed/novis_test/val
python run.py --config configs/fusion_full.yaml --ckpt checkpoints/novis_real/best.pt
```

`eval.py` writes `results/metrics.json` and a picture grid at
`results/samples/eval_grid.png`. That grid is the figure the paper wants:
sensor input on one side, the model's reconstruction, and the real photo.

If you prepared a `stress/` split (`--r-use`, Section 12), also run:

```bash
python eval.py --config configs/fusion_full.yaml --ckpt checkpoints/novis_real/best.pt ^
    --data shards --val-shards data/processed/novis/stress
```

Report both numbers side by side, not just the in-range one: it turns "the
sensors have limited range" from a disclaimer into a measured, graceful
degradation result.

### 14.4 Practical notes

- Interrupted runs continue with `--resume checkpoints/<run>/latest.pt`; the
  trainer writes full resumable state at the end of every epoch.
- `best.pt` holds the EMA (release) weights, and that is what eval, export and
  the server load.
- With only a few thousand real samples, **watch for overfitting**: if
  validation loss turns upward while training loss keeps falling, cut the
  epochs (`--epochs 15`) rather than letting it run to 40.
- If for some reason the public-data pretraining never happens, you can still
  train Stage D from scratch on real data alone — but say so plainly in the
  paper and expect blurry, structure-only reconstructions. A 27 M-parameter
  model does not learn vision from 3,000 images.

### 14.5 The two-channel thermal change (laptop track, parallel to capture)

Decision D3/D4 (§0.5). None of this blocks a capture session — do it while the
sessions are happening. In order, smallest first:

| # | File | Change |
|---|---|---|
| 1 | `src/novis/models/stems.py` | `ThermalStem`: take an `in_ch` argument; `nn.Conv2d(1, ...)` becomes `nn.Conv2d(in_ch, ...)`. One line plus the parameter. |
| 2 | `src/novis/data/dataset.py` | `thermal` documented and shaped `(2,24,32)`. |
| 3 | `src/novis/data/degradation.py` | Add a centre-crop helper that makes the BAB-like channel from one public thermal image, at the measured BAA:BAB FOV ratio (§4.2). |
| 4 | `scripts/prepare_llvip.py` | Emit 2-channel thermal: whole image -> ch0, centre crop -> ch1, `degrade_thermal()` on each. |
| 5 | `scripts/prepare_novis.py` | Emit 2-channel thermal from the real pair (`thermal`, `thermalFar`). |
| 6 | `scripts/check_novis_shards.py` | `EXPECT["thermal"]` -> `(2,24,32)`; report per-channel liveness so a dead BAB shows up as a dead channel, not as noise. |
| 7 | `configs/` | Nothing, unless a channel count gets hard-coded somewhere. |

Then re-run Stage A with the new shape. **Keep the one-channel checkpoints** —
one-channel vs two-channel on the same captures is the ablation §15 asks for.

A caution worth stating up front: two channels is the better-motivated design,
but it is not automatically the better *result* on a few thousand real
samples. If the ablation says one channel wins, report that honestly — a
negative result that is properly measured is still a result, and the fallback
path is already built.

---

## 15. What to report in the paper

Fill these in from the capture files and the notes, not from memory:

- Number of **scenes** and number of **samples**, and the fact that they are
  different things (25 samples share one photo)
- Number of physically distinct **rooms**, and which rooms were held out
- The split: train / val / test, by scene, with the held-out room names
- Sensor FOV, phone lens and zoom setting, and how they were matched
  (Section 4.2), **and the measured usable ranges R_A and R_B** (§4.2b/4.2c)
- Both sensors' FOV, the FOV ratio, the fact that photos were framed to BAB
  (decision D2), and the mounting geometry (co-axial, D1). If the one-channel
  fallback was used anywhere: the
  `--baa-max-range` crossover distance, and how many samples came from each
  sensor (`prepare_novis.py`'s printed summary)
- Near / mid / far / beyond-R_B sample counts, and, if a `stress`
  split was evaluated, the in-range vs. beyond-range metrics side by side —
  the graceful-degradation result Section 8 and 14.3 set up for
- Module height, and that it was constant
- Fraction of scenes containing a person; consent and ethics status
- Thermal normalisation choice, and the fixed-vs-perframe comparison
- The known limitations, stated up front: no depth ground truth (the node has
  no depth sensor, so `depth_valid` is all zeros and the depth loss is
  masked); colour is inferred from priors, not measured; the placeholder
  encryption key means the current build is **not** described as secure

---

## 16. Mistakes that cost a whole session

| Mistake | What happens | Prevention |
|---|---|---|
| Closing or reloading the browser tab before downloading | Every sample since the last download is gone | Download every ~10 scenes; the page now warns you, but do not rely on it |
| Photo taken from a different position than the module | The model is asked to predict something its inputs never saw | Photograph from the module's own viewpoint, every time |
| Changing phone lens/zoom mid-project | Two incompatible halves of a dataset | Lock the setting on day one and write it down |
| One room, many scenes | Cannot make an honest train/test split | At least 6-8 different rooms; decide the test rooms on day one |
| Someone walks through during capture | Sensor data and photo disagree | Keep the scene still for the full 25 s |
| Thermal NOT FOUND, unnoticed | Samples get dropped downstream | The page now refuses to capture — but check the panel anyway |
| Reusing a scene id for a different room | Two different rooms share one photo, and the split leaks | Use `room-arrangement-viewpoint`; `check_novis_shards.py` will catch it |
| Collecting everything before checking the pipeline once | A systematic fault in every file | Do the 3-scene pilot in Section 9 first |
| Leaving ethics paperwork until the end | People-scenes unusable | Start it now; collect people-free scenes meanwhile |
| Photographing a whole big room as one scene, well beyond R_B | Model trained to hallucinate detail the sensors never carried | Measure R_A/R_B (4.2b); split a big room into several in-range positions instead (Section 8) |
| Framing a photo to BAA instead of BAB | Periphery of every far photo has no sensor behind it; unfixable afterwards | Zoom locked to BAB on day one (4.2); the frame-check pane shows BAB |
| Capturing while BAB reads NOT FOUND | No valid framing reference at all | Both panels must say sensor OK before any scene (checklist) |
| Leaving "main surface distance (m)" blank | `--r-use` cannot bucket that scene | Fill it in every scene — tape measure or the sonar panel |
| Stopping a session to "fix" a dead pixel | Days lost to a documented part tolerance that is already repaired for you | One or two fixed dots are normal (4.2d) — note them and carry on |

---

## 17. Printable session checklist

> **Superseded 24 Sept 2026** — use the pocket checklist at the end of
> [`session1_baa_capture.md`](session1_baa_capture.md), which is BAA-centred.
> The list below is kept for the two-sensor setup it was written for.

Keep this open on the phone.

**Setup**
- [ ] Module on battery, at the standard height, marked
- [ ] Joined `NOVIS-B6`, dashboard open at `http://192.168.4.1/`
- [ ] **BAA** says **sensor OK**. (Superseded line: this used to require BAB
      too, because BAB defined the framing. It no longer does — BAB being down
      does not stop a session.)
- [ ] BAA and BAB agree on a mug dead ahead (mounting still straight)
- [ ] Sonar numbers match a tape measure against a wall
- [ ] Echo badge says **echo return detected**
- [ ] Phone camera: zoom **locked to BAB's FOV**, HDR off, night mode off
- [ ] R_A and R_B measured and written in `hardware_log.md` (§4.2b, §4.2c)
- [ ] Consent in place for any scene with a person

**Each scene**
- [ ] Module placed; scene id typed
- [ ] Scene notes filled — **distance in metres matters most**, it drives
      every bucket downstream
- [ ] Photo taken from the module's viewpoint, framed to BAB
- [ ] **Side-by-side frame check passed** — warm object in the same grid box
      on the photo and on **BAB's** pane
- [ ] Stepped out of view
- [ ] "Capture a scene (25)" pressed; stood still until "scene done"
- [ ] Quality pills checked (echo returns, sonar valid)
- [ ] Echo distance roughly agrees with sonar

**Every ~10 scenes**
- [ ] Downloaded the dataset `.json`

**End of session**
- [ ] Final `.json` and summary `.csv` downloaded
- [ ] Files copied into `data/real_capture/` **and** backed up elsewhere
- [ ] `prepare_novis.py` run
- [ ] `check_novis_shards.py` run and clean
- [ ] Session notes written: rooms, scene count, anything odd, ids to drop
