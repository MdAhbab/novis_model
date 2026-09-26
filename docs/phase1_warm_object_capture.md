# Phase 1 — start with what the sensors can actually see

**The problem this solves:** a room at rest is all one temperature, so thermal
sees no furniture, no walls, no doors. It sees warm things. Trying to learn
"draw this room" from that is learning from a signal that is not there.

**So do not start there.** Start with the thing the sensors resolve cleanly —
**where is the warm thing** — and get a real, measurable result out of it.

This does not replace the room work. It is the first phase of it, it uses the
same rig and the same 25-sample loop, and **none of it is wasted** if a sonar
sweep or a second microphone is added later.

> Mechanics — setup, the hot-mug zoom lock, R_A, the capture loop, downloads —
> are all unchanged. Follow [`session1_baa_capture.md`](session1_baa_capture.md)
> for those. This document only changes **what you point the module at**.

---

## Why a warm object beats a person, for the first session

| | Person | **Hot water bottle** |
|---|---|---|
| Consent paperwork | required | **none** |
| Stays still for 25 s | tries to | **perfectly** |
| Position accuracy | "about there" | **tape-measured, exact** |
| Gets tired after 2 hours | yes | **no** |
| Repeatable next week | not exactly | **exactly** |

A filled hot water bottle is roughly torso-sized and roughly torso-temperature.
It is the best human stand-in you can buy, and it lets you build a precise grid
in one afternoon with nobody standing around.

**Good warm targets**, roughly in order of usefulness:

1. **Hot water bottle** — torso-sized, stays warm ~1 hour, safe, cheap
2. **Mug of just-boiled water** — small and sharp, good for precise positions,
   needs refilling every ~20 min
3. **Laptop running something heavy** — realistic, stays warm indefinitely
4. **Desk lamp (incandescent)** — very hot, very visible, realistic object
5. **A person** — save for phase 2, once the pipeline is proven

---

## What you are actually measuring

Put the warm object at known positions on a grid and record the scene. The
result you get out of this is a real number:

> *"The system locates a heat source to within X cm at Y m, from thermal +
> sonar + echo, with no camera."*

That is quantitative, honest, and defensible. It is a far stronger claim than a
blurry room image produced from two sonar readings.

### The grid

Lay a tape measure on the floor. Mark the module's straight-ahead line as
**x = 0**, then mark left and right offsets.

```
                    module
                      |
       -90  -45   0  +45  +90   cm      <- lateral offset
        |    |    |   |    |
        .    .    .   .    .            <- 1.0 m
        .    .    .   .    .            <- 1.5 m
        .    .    .   .    .            <- 2.0 m
```

**15 positions.** All of them sit inside BAA's view — the wide lens reaches:

| distance | BAA half-width | where ±90 cm lands |
|---|---|---|
| 1.0 m | ±143 cm | 63% out toward the edge |
| 1.5 m | ±214 cm | 42% out |
| 2.0 m | ±286 cm | **only 32% out** |

So at 2.0 m the object never leaves the middle of the frame, and the edges of
the picture never get used. **Add two extra scenes at 2.0 m, at ±150 cm**, so
the far row exercises the frame like the near row does:

```
   grid-d200-xm150      grid-d200-xp150
```

That makes **17 scenes** in the grid. Keep every position inside R_A.

### Scene ids encode the position

Use this exact format so the positions can be parsed out later:

```
   grid-d<distance in cm>-x<m|p|0><offset in cm>

   grid-d100-xm90     1.0 m, 90 cm LEFT   (m = minus)
   grid-d150-x000     1.5 m, centre
   grid-d200-xp45     2.0 m, 45 cm RIGHT  (p = plus)
```

Put the object and its height in the **note** field, every time:

```
   note: hot water bottle, 75 cm above floor
```

And put the **object's** distance in the distance field — not the wall's. For
these scenes the object is the subject.

---

## Session plan — about 27 scenes, ~2 hours

| # | Scenes | What | Why |
|---|---|---|---|
| 1 | 17 | the full grid above, one hot water bottle | the core localisation result |
| 2 | 4 | **empty room**, same viewpoints, nothing warm | the negative case — "nothing there" must be learnable too |
| 3 | 3 | **two** warm objects at once | does it separate them, or blur them into one? |
| 4 | 3 | same positions, **different object** (lamp, laptop) | does it generalise past one object, or memorise it? |

Rows 2–4 are what stop this being a toy. Without empty scenes the model never
learns "nothing is there". Without a second object it may just memorise the
bottle's exact shape.

**Keep the room itself unchanged for the whole session.** One variable at a
time — this session the variable is *where the heat is*.

---

## Do this first: the 15-minute sensor check

Before the grid, find out whether sonar and echo carry anything at all. If they
do not, that is a hardware problem and no amount of capture will fix it.

Point the module at three genuinely different things and write down the
readings the dashboard shows:

| Scene | sonar L | sonar R | echo distance |
|---|---|---|---|
| a wall, 1 m away | | | |
| open room, 3 m+ | | | |
| into a corner | | | |

- **Numbers clearly different** → geometry is being sensed, go ahead
- **Numbers nearly identical** → stop and fix the hardware first

Do the same with the warm object at `x=-90` and `x=+90`: **the thermal hotspot
readout should move across the frame.** If it does not, the grid will not work.

---

## What this phase does and does not give you

**Does:**
- A measurable heat-source localisation result from a camera-free node
- A working, proven end-to-end pipeline — capture, previews, shards, training
- Data that stays valid under every later decision

**Does not:**
- Room geometry. Furniture and walls stay invisible until either a sonar sweep
  or a second microphone is added, or the goal is reframed to a *known* room.

That is the honest boundary, and knowing where it sits is worth more than
guessing.

---

## Phase 2 and after

1. **Phase 2 — people.** Same grid, with a person instead of the bottle.
   Standing, sitting, facing toward/away. Consent wording is in
   `NOVIS_Build_Guide.md` Part E5. The bottle grid tells you what accuracy to
   expect before anyone stands in a room for two hours.
2. **Phase 3 — room state, one of:**
   - **Known-room framing** (free): the model learns one room; the sensors
     report its state — someone present, where, door open. This is the real
     use case for an assistive device in someone's own home.
   - **Sonar sweep** (~1 servo): sweep the sonar across BAA's view during the
     25-second capture. Turns 2 range numbers into ~23 angled ones. The single
     biggest geometric gain available.
   - **Second microphone** (~1 INMP441): true binaural echo, which is how
     BatVision recovers layout. `EchoStem` already expects 2 channels and is
     currently fed the same mono channel twice.
