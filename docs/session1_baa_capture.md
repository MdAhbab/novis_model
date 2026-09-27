                                                        # Session 1 — BAA-centred capture

**This is the only document you need on a capture day.** It replaces the
BAB-centred framing rules in `data_collection_protocol.md` (that file is still
correct about everything else — scene variety, the shard pipeline, the paper
table — but where the two disagree about *which sensor the photo is framed to*,
**this one wins**).

Written to be read on a phone, in a room, with the module already on.

---

## Why BAA, and not BAB

**BAA is the sensor. Every photo is framed to BAA. BAB is recorded but nothing
is decided from it.**

The first reason for this was that BAB's dead pixel washed its panel out to
flat yellow. **That is fixed and flashed** — BAB now displays properly. The
decision stands anyway, on a stronger reason that does not go away:

```
   BAB's thermal reach        ~8 m
   HC-SR04 sonar hard cap      4 m      <- SONAR_MAX_M = 4.0
```

**Past 4 m the sonar returns nothing at all.** A scene at 6 m would have
thermal but no sonar and a near-useless echo — that is not multimodal
reconstruction any more, it is drawing a room from a heat map. BAB's extra
reach is range the rest of the module cannot support.

R_A (~2.5–3 m) matches what the *whole module* can actually sense. BAA is also
the wide sensor, so each scene covers more of a room and fewer scenes are
needed per room.

| | BAB-centred | **BAA-centred (this plan)** |
|---|---|---|
| Photo framed to | BAB (narrow) | **BAA (wide)** |
| Model thermal input | 2 channels — needs new code | **1 channel — already works** |
| Scene distance | ~8 m, mostly past the sonar | **R_A, fully supported** |
| Scenes per room | more | **fewer** |

### BAB is still being recorded, on every single sample

You do not have to do anything for this — the firmware stores `thermalFar`
alongside BAA automatically. It costs nothing and keeps the **two-sensor
comparison available later on this exact dataset**, with no re-capture.

`prepare_novis.py` reports BAB's coverage on every run, so if BAB ever dies
mid-session you find out that evening rather than in three months.

### Two things that are NOT problems

1. **A fixed dot on a panel is a dead pixel — normal, not a fault.** MLX90640
   parts ship with a few as a documented tolerance. `prepare_novis.py` repairs
   them from neighbouring pixels automatically. A `min` of `-0.0 °C` next to a
   normal-looking picture is exactly what a dead pixel looks like.
2. **No pilot run on the PC is needed.** Replaced by the 2-minute pilot in
   Step 4 below, which needs only the phone. Do not skip it.

---

## The three rules

1. **Lock the phone zoom on day one. Never change it again.** A consistent
   framing error is harmless — the model learns it. An *inconsistent* one
   splits your dataset in half and cannot be fixed afterwards.
2. **Every scene's main surface must be within R_A** (you measure R_A in
   Step 3). Past that the sensors carry nothing, and the photo teaches the
   model to invent detail it can never sense.
3. **Photograph from the module's own position.** Phone lens within ~5 cm of
   the thermal sensor, same height, same direction.

---

## What you need

- [ ] The module, on battery, charged
- [ ] A stable stand — tripod, stack of books, shelf — at a fixed height
- [ ] Tape measure (a phone measuring app is not accurate enough for R_A)
- [ ] **A mug of just-boiled water** — this is your calibration tool, do not skip it
- [ ] Masking tape or sticky notes
- [ ] A helper (much faster, but doable alone)
- [ ] A paper notebook and pen
- [ ] The phone, charged, with ~50 MB storage free

---

## Step 1 — Set up the module (10 min)

1. Put the module on the stand at roughly **chest height (~1.2 m)**. Measure it.
   **Write the number down. Use the same height for the whole project.**
2. Power on. Wait ~10 seconds.
3. On the phone, join the WiFi network:
   - **Network:** `NOVIS-B6`
   - **Password:** `novis1234`
4. Open a browser and go to **`192.168.4.1`**
5. Check these four things before doing anything else:

   | Panel | What you want to see |
   |---|---|
   | **Thermal BAA** | pill says `sensor OK`, picture changes when you wave a hand |
   | Sonar | two numbers that change as you move a hand in front |
   | Echo | **`echo returns` pill above 0** — the `spike` flag alone is not proof the echo works |
   | Thermal BAB | `sensor OK` — you do not frame to it, but it should be alive |
   | Mixed | shows a picture once BAA and BAB both do — see below |

6. **One quick look at BAA's panel:** wave your warm hand across the view. Does
   any dot stay frozen in place while everything else moves? If yes, BAA has a
   dead pixel too — **write down roughly where it is and carry on.** It will be
   repaired automatically at prepare time. It stops nothing today.

7. **Left/right sanity check:** wave your hand to the **right** of the module.
   It should light up on the **right** side of BAA's panel. If it lights up on
   the left instead, the dashboard is not the current build — reflash it
   before capturing; do not work around it by mentally flipping the picture,
   since the recorded `.json` and every downstream number assume this check
   already passed.

**A third panel, "Mixed",** sits below BAB. It shows BAA's whole view with
BAB's sharper pixels filling the outlined middle — like the sharp centre of
one eye against its wide blurry edge, not stereo, there is no depth in it.
It needs nothing from you; both sensors are already being read. Its own hint
text has the details. It is a live *preview* only — it does not change what
gets captured or stored, and it does not repair dead pixels the way
`prepare_novis.py` does afterwards, so a known dead pixel (BAB's, for
example) will still show there and correctly turns its status pill red.

If BAA says `NOT FOUND`, power-cycle the module once. If it still says NOT
FOUND, check the GPIO21/22 wiring — do not capture without BAA.

---

## Step 2 — Lock the phone to BAA's view (25 min, ONCE EVER)

This is the most important half hour of the project. Everything after it is
repetition.

**The idea:** BAA sees a certain rectangle of the world. The photo needs to be
that same rectangle. A hot mug lets you see exactly where BAA's edges are.

1. Find a **blank wall**. Put the module **1.20 m** from it (tape measure),
   pointing straight at it, at your marked height.
2. Fill the mug with just-boiled water.
3. Hold the mug **against the wall, at the sensor's height**, starting well
   outside the left edge of what BAA sees. Slide it slowly right.
4. Watch BAA's panel. **The moment a bright blob first appears at the very left
   edge of the picture — stop. Stick a note on the wall there.**
5. Repeat from the right side. Then from above, and from below.

You now have four marks. **That rectangle is exactly what BAA sees at 1.2 m.**

6. Now put the **phone** where the module was — lens as close as you can to
   where the thermal sensor sits. **Landscape. 4:3 aspect ratio, not 16:9**
   (the thermal sensor is 32×24, which is 4:3 — this matters).
7. Try **0.5x (ultra-wide)** first. Do the four marks sit on the four edges of
   the phone's frame?
   - **Marks land on the edges** → that is your zoom. Done.
   - **Phone frame is wider than the marks** → zoom in slightly (0.6x, 0.7x)
     until the marks reach the edges.
   - **Phone frame is still narrower than the marks even at 0.5x** → use 0.5x
     anyway and **write down: "photo is a centre crop of BAA."** This is fine.
     A photo narrower than the thermal view is the safe direction — the model
     gets extra context, never missing context.

8. **Write the zoom setting in the notebook, in pen, and never change it.**
   Also write down which camera app and which aspect ratio.

> **Why a hot mug and not eyeballing it:** even on a washed-out display, boiling
> water is far hotter than anything else in the room, so it stays clearly
> visible. The mug test works even when the panel looks broken.

**Expected result, as a sanity check:** BAA is the wide variant (about
110° × 75°), so at 1.2 m it should cover roughly **3.4 m wide × 1.8 m tall**.
Most phone ultra-wide lenses land close to this. If your marks are wildly
different, re-measure the 1.2 m before trusting the result.

---

## Step 3 — Find R_A, how far BAA actually sees (10 min, ONCE EVER)

A person is the real target, so use a person — not the mug.

1. Clear a straight line 4 m long. Mark 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0 m
   with tape.
2. The helper stands at each mark in turn, facing the module.
3. At each distance, look at BAA's panel and ask **one** question:
   *Can I see a clearly person-shaped warm region, separate from the background
   — not just a vague smudge?*
4. **The last distance where the answer is still YES is R_A.**

Write R_A in the notebook. Expect **2.5–3.0 m** based on what you have seen so
far. If it comes out above 4.0 m, cap it at 4.0 m anyway — the sonar cannot see
past that, so nothing beyond it is usable regardless.

### While you are at it, write down R_B too

The helper is already standing at each mark and **both panels are on screen**,
so this costs nothing. At every distance, answer the same question for **BAB**
as well, and write **two numbers** instead of one:

```
   distance   BAA clear?   BAB clear?
   1.0 m         yes          yes
   1.5 m         yes          yes
   2.0 m         yes          yes
   2.5 m         yes          yes
   3.0 m         no  <- R_A   yes
   3.5 m          -           yes
   4.0 m          -           yes  <- R_B is at least 4.0 m
```

**R_B changes nothing about today.** Scenes are still planned against R_A, the
photo is still framed to BAA. This is purely for the record.

**Why bother:** BAB is being recorded on every sample anyway, so the
two-sensor comparison stays possible later on this exact dataset — but only if
R_B was measured. Re-measuring it in three months means setting the whole rig
back up in the same room. Two minutes now saves that.

If the room lets you, walk past 4.0 m for BAB alone and note where it finally
gives up. If it does not, write **"R_B ≥ 4.0 m, not measured further"** — an
honest bound is worth more than a guess.

**From now on: no scene's main surface is further than R_A.** If a wall you
want is 5 m away, do not shoot the whole room from one spot — move closer and
make it two scenes instead.

---

## How capture actually works — read this once, it removes all the guesswork

Three things confuse everyone the first time. Here is exactly what happens.

### One photo per scene, not 25

**You take ONE photo. The node takes 25 sensor readings of it.**

```
   bedroom01-a-v1
   ├── photo.jpg        <- 1 photo, taken by YOU, before you press capture
   └── 25 samples       <- taken by the NODE, automatically, over ~20-25 s
         each one = thermal BAA + thermal BAB + 2 sonar + 1 echo
         all 25 point back at that same one photo
```

You do **not** click the camera 25 times. You click it **once**, attach it,
then press "Capture a scene (25)" and stand still.

**Why 25 and not 1?** The sensors are noisy. 25 readings of the same still room
are 25 slightly different inputs that all map to the same correct answer — so
the model learns "these all mean that room" instead of memorising one exact
reading. It is free training data and it costs you 25 seconds.

### What you actually do, in order

| | Who does it | How long |
|---|---|---|
| 1. Fill scene id, distance, note | you | ~30 s |
| 2. Take the photo, attach it | you | ~1 min |
| 3. Check photo vs BAA panel | you | ~15 s |
| 4. Press "Capture a scene (25)" | you, once | 1 click |
| 5. **Stand still, don't move** | nobody | **~20-25 s** |
| 6. It stops on its own | the page | — |

Step 5 is the only waiting, and yes — **every scene**. It is 25 seconds, and it
is the part that must not be rushed. Anyone walking through during it puts a
person in the sensor data who is not in the photo.

Total ≈ 5 minutes per scene. 14 scenes ≈ 2 hours with breaks.

### The 25 finished — now what? (you do NOT download)

Nothing to press. The burst stops by itself. To start the next scene:

```
   25 done  ->  type the NEW scene id  ->  photo clears by itself
                                           pill turns red:
                                           "new scene - needs a photo"
                         |
                         v
            fill distance + note  ->  take + attach the new photo
                         |
                         v
            press "Capture a scene (25)"  ->  stand still 25 s
                         |
                         v
                    repeat, 14 times
```

**Changing the scene id is the whole transition.** The page clears the previous
photo the moment you type a different id — deliberately, so the last scene's
picture can never become this scene's training target by accident. If the pill
still says *"photo attached"* after you typed the new id, you did not actually
change the id. Check it.

Three things worth knowing:

- **`N in this scene`** next to the capture button should read **25** when a
  scene is done. If it says less, the burst was interrupted — press capture
  again to top it up.
- **Re-typing an old scene id brings that scene back** — its photo, distance,
  lighting and note all reload. Useful if you want more samples of a scene you
  already did. Its original photo is kept, not replaced.
- **Pressing capture twice without changing the id** adds another 25 samples to
  the same scene. Harmless, just not useful.

### Saving a scene as a picture, on the phone

Everything you type into the scene form — **scene id, room, distance, people,
lighting, note** — is stored in the `.json`, in its `scenes` block, alongside
the photo itself. Nothing is lost, and you never have to download photos
separately.

But the `.json` is not something you can *look at* on a phone. So there are
two buttons next to the capture button:

- **"Save scene .png"** — one picture: your photo beside the averaged BAA
  frame, with the readings printed under it.
- **"Save photo .jpg"** — just the plain photo, exactly as it sits in the
  `.json`. No thermal, no composition.

```
   +------------------------+--------+
   |                        |        |
   |      your photo        | BAA    |   <- averaged over the scene's 25 frames
   |                        |        |
   +------------------------+--------+
   | grid-d150-xp45  lab  1.5 m  0 people  dim          |
   | BAA 29.6-36.0 C over 25 frames                     |
   |   sonar L 1492 mm / R 1508 mm   echo returns 20/25 |
   | note: hot water bottle, 75 cm                      |
   +----------------------------------------------------+
```

**Both are optional.** The `.json` already holds all of it, and
`scripts/export_scene_previews.py` builds the same pictures for every scene at
once on the laptop, plus a third panel — the merged BAA+BAB frame — that
these two phone-side buttons do not. Use them when you want to keep, check or
send one scene on the spot — no laptop, no waiting until evening.

**File names never collide.** Both buttons save as
`novis_<scene id>_<timestamp>.png` / `.jpg` — for example
`novis_grid-d150-xp45_2026-09-27T10-15-30.png`. Saving the same scene twice
(topping up samples, redoing a shot) always gets a fresh timestamp, so the
phone never has to silently rename a file `(1)`, `(2)`… and Downloads sorts
in the order you actually captured, even across different sessions that
reused a scene id.

### Downloading: NOT after every scene

**Every download contains the whole session, not just what is new.**

```
  after scene 7   ->  file #1  =  scenes 1-7
  after scene 14  ->  file #2  =  scenes 1-14      <- contains file #1 entirely
```

So downloading after every scene gives you 14 files that each swallow the last
one. Pointless, and it fills the phone.

**Download twice: once around scene 7, once at the end.** The middle one is
pure insurance — if the tab dies at scene 12 you have lost 5 scenes instead of
12. The final one is the real file.

> **Keeping both files is safe.** `prepare_novis.py` recognises samples it has
> already seen (by scene id + frame counter) and ignores the overlap — it will
> print `50 already seen in an earlier file`, which is normal, not a warning.
> You never have to work out which file to keep or delete.

**What you must not do** is close or reload the tab without downloading. The
samples live in the browser tab only. A reload wipes them.

---

## Step 4 — The 2-minute pilot (DO NOT SKIP)

Without a PC you cannot check the shards, so check the file instead. This
catches a systematic mistake now instead of after 15 scenes.

1. Do **one complete scene**, following Step 5 below exactly.
2. Immediately press **"Download dataset .json"**.
3. Open the downloaded file on the phone (any file manager or text viewer).
4. Check three things:

   | Check | Good | Bad |
   |---|---|---|
   | File size | **more than 1 MB** | a few KB → the photo did not attach |
   | Search for `"scenes"` | found, with your scene id | missing → scene not saved |
   | Search for `data:image` | found, a very long string | missing → no photo |

5. If all three pass — **you are clear to run the whole session.** The pilot
   scene counts as scene 1; downloading does not erase anything.
6. If any fail, fix it now and redo the pilot. Do not carry on and hope.

---

## Step 5 — The scene loop (repeat for every scene)

About 5 minutes per scene once you are in rhythm.

1. **Place the module** at the viewpoint, at the marked height, pointing at the
   scene. Stable — it must not move for the next minute.
2. **Measure the main surface distance** with the tape measure. **Must be
   ≤ R_A.** If it is not, move closer.
3. **Fill the scene form** on the dashboard:
   - **scene id** — `room-arrangement-viewpoint`, e.g. `bedroom01-a-v3`
   - **room / place** — e.g. `bedroom`
   - **main surface distance (m)** — the number you just measured. **Never
     leave this blank**, the whole range analysis depends on it.
   - **people in view** — 0, 1, 2...
   - **lighting** — normal / bright / dim / dark
   - **note** — say what is warm in the scene: *"laptop on desk, no person"*,
     *"radiator on, curtains closed"*. Worth writing properly.
4. **Take the photo.** Phone at the module's position, **locked zoom**,
   landscape, 4:3. Then attach it with **"Take / choose photo"**.
5. **Check the photo against BAA's panel.** Are the same objects at the same
   left and right edges? If the photo shows a chair that BAA does not see at
   all, the framing has drifted — go back and re-shoot.
6. **Everyone stands still.** Press **"Capture a scene (25)"**. It takes about
   **20–25 seconds** and stops on its own. Nothing moves, nobody walks through.
7. **Write it in the paper notebook too:** scene id, distance, what was in it.
   Thirty seconds now saves an hour of guessing later.

### The one thing that ruins a scene silently

Someone walking through during those 25 seconds. The sensors record a person;
the photo does not have one. That pair teaches the model something false. If it
happens, redo the scene — do not keep it.

---

## Step 6 — Today's scenes: one room, 14 of them

**One room only today.** One room done properly beats three rooms done badly.

Fill in your room name and work down the list. Change **one thing** between
scenes — that is what makes the dataset teach anything.

| # | scene id | viewpoint | what is different |
|---|---|---|---|
| 1 | `<room>-a-v1` | corner 1, facing in | baseline, lights on |
| 2 | `<room>-a-v2` | corner 2 | — |
| 3 | `<room>-a-v3` | corner 3 | — |
| 4 | `<room>-a-v4` | facing the bed / sofa | — |
| 5 | `<room>-a-v5` | facing the desk / table | — |
| 6 | `<room>-a-v6` | facing the door | — |
| 7 | `<room>-b-v1` | corner 1 again | **lights off** |
| 8 | `<room>-b-v4` | facing bed again | **lights off** |
| 9 | `<room>-c-v1` | corner 1 again | **one person sitting** |
| 10 | `<room>-c-v4` | facing bed again | **one person standing** |
| 11 | `<room>-d-v1` | corner 1 again | **chair / objects moved** |
| 12 | `<room>-d-v5` | facing desk again | **desk rearranged** |
| 13 | `<room>-e-v5` | facing desk | **hot laptop or mug on the desk** |
| 14 | `<room>-e-v6` | facing door | **door open** (was closed) |

**Keep roughly half the scenes with something clearly warm in view** (person,
laptop, mug, radiator, lamp) and half without. A room at one uniform
temperature gives the thermal channel almost nothing — which is a real and
honest test case, but if *every* scene is like that, the thermal input teaches
nothing at all. Say which it is in the note field every time.

**Download the `.json` after scene 7, and again at the end — twice, not
fourteen times.** Each download holds the whole session, so the second one
contains the first. Keeping both is safe; see *"Downloading: NOT after every
scene"* above.

---

## Step 7 — End of session (10 min, do not skip)

1. **Download the `.json`.** Then download it again — two copies.
2. **Get one copy off the phone right now.** Email it to yourself, or put it in
   Drive. A phone is a single point of failure for a whole day's work.
3. Only once both copies exist, close the browser tab.
4. **Write the session log** in the notebook:

```
Date:              ____________________
Room:              ____________________
Module height:     ______ m
Phone zoom locked: ______   aspect: 4:3   camera app: __________
Photo = centre crop of BAA?   yes / no
R_A measured:      ______ m   (BAA - this is the one that limits scenes)
R_B measured:      ______ m   (BAB - record only, not used today)
BAA dead pixel?    none / at approx (__,__)
BAB dead pixel?    none / at approx (__,__)
Scenes captured:   ______
Scene ids:         ____________________________________________
Anything odd:      ____________________________________________
```

Those numbers are needed for the paper and cannot be recovered later. Write
them down while still in the room.

---

## If something goes wrong

| What you see | What it means | Do this |
|---|---|---|
| BAA panel `NOT FOUND` | sensor not answering | power-cycle once; then check GPIO21/22 |
| Capture button refuses | no scene id, or no photo attached | fill the scene id and attach the photo |
| "sensor frame is stale" | dashboard lost the module | reload the page — **but download first if you have unsaved scenes** |
| Sonar reads 0 / 0 | nothing in range, or wiring | check something is within 4 m; wave a hand |
| Panel looks flat / washed out | a dead pixel dragging the colour scale | **ignore it, the data is fine** |
| A dot frozen in one place | dead pixel | note it, carry on — repaired at prepare time |
| Phone dropped the WiFi | AP restarted | rejoin `NOVIS-B6`; **samples in the tab survive a reconnect, but not a reload** |
| Browser tab closed by accident | everything since the last download is gone | download every ~7 scenes so this costs little |

---

## When you are back at the laptop

Four commands, in this order. All of them are numpy/Pillow only — **no torch,
no GPU, nothing heavy.** Everything stays on D:.

**1. Get the files off C: and into the project**

```bash
python scripts/ingest_capture.py --session session01
```

Finds `novis_dataset_*.json` in your Downloads folder and **moves** them to
`data/real_capture/session01/`. It refuses to overwrite, skips byte-identical
duplicates, and tells you how many scenes and photos each file actually
contains before moving it.

**2. Look at every scene — do this the same evening**

```bash
python scripts/export_scene_previews.py --captures "data/real_capture/session01/*.json"
```

Then open `data/previews/index.html`. Each scene is one row: **the photo on the
left, what BAA actually saw on the right.**

This is the check that matters. A framing mistake is invisible in the numbers
and obvious here — if a warm body sits centre-left in the photo and centre-right
in the thermal, that scene is misframed. Do this while the room can still be
re-shot, not a month later.

The third panel is the **merged frame**: BAA's whole view with BAB's sharper
pixels in the outlined centre, like the sharp middle of an eye. It needs
nothing extra at capture time - both sensors are already recorded.

It also writes, per scene, `photo.jpg` + `thermal_baa.png` + `thermal_bab.png`
+ `thermal_merged.png` + `pair.jpg`, and a `scenes.csv` of every scene with its distance, lighting,
note and temperature range.

**3. Build the shards — the default is already BAA-only**

```bash
python scripts/prepare_novis.py --captures "data/real_capture/session01/*.json" ^
    --out data/processed/novis --r-use <your R_A>
```

Do **not** pass `--baa-max-range`. Leaving it off means every scene uses BAA,
which is the plan. Dead-pixel repair runs automatically — copy the two lines it
prints into the session log.

**4. Check before training**

```bash
python scripts/check_novis_shards.py data/processed/novis
```

**Training does not happen on this laptop** — no GPU. Steps 1–4 are the whole
laptop job; the shards get copied to a GPU machine afterwards.

Also, when convenient: flash the updated dashboard (`firmware/dashboard/`) so
the washed-out panel and the dead pixel stop being visible. Framing and
procedure do not change.

---

## Pocket checklist

**Once, at the start**
- [ ] Module height measured and written down
- [ ] BAA says `sensor OK`
- [ ] Phone zoom locked with the hot-mug test, written down
- [ ] R_A measured, written down (and R_B, while the helper is there)
- [ ] 2-minute pilot passed (file > 1 MB, has `"scenes"`, has `data:image`)

**Every single scene**
- [ ] Distance measured, and **≤ R_A**
- [ ] Scene id filled, in `room-arrangement-viewpoint` form
- [ ] **Distance field filled in** — not blank
- [ ] Note says what is warm in the scene
- [ ] **One** photo taken from the module's position, at the locked zoom
- [ ] Photo edges match BAA's panel edges
- [ ] Everyone still for the full 25 seconds, every scene
- [ ] Scene written in the paper notebook

**Mid-session**
- [ ] `.json` downloaded once around scene 7 (insurance)

**At the end**
- [ ] `.json` downloaded again — this one is the real file
- [ ] One copy off the phone
- [ ] Session log written
