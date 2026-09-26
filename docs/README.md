# NOVIS documentation — what to read, and when

Seven documents, and most days you need exactly one of them. Start here.

## Start here if thermal only shows people

**[`phase1_warm_object_capture.md`](phase1_warm_object_capture.md)** — a room
at rest is all one temperature, so thermal sees no furniture. Phase 1 starts
with what the sensors *do* resolve: where the warm thing is. A tape-measured
grid with a hot water bottle, no consent paperwork, and a real number at the
end. Uses the same rig and loop as below.

## On a capture day

**[`session1_baa_capture.md`](session1_baa_capture.md)** — the only thing you
need in the room. Setup, the hot-mug zoom lock, measuring R_A, how capture
actually works (one photo per scene, 25 sensor samples, when to download), the
scene loop, the end-of-session routine, and a pocket checklist. Written to be
read on a phone. Needs no PC.

## Back at the laptop, after a session

Same document, section **"When you are back at the laptop"** — four commands,
all numpy/Pillow only, no GPU:

```bash
python scripts/ingest_capture.py --session session01
python scripts/export_scene_previews.py --captures "data/real_capture/session01/*.json"
python scripts/prepare_novis.py --captures "data/real_capture/session01/*.json" ^
    --out data/processed/novis --r-use <R_A>
python scripts/check_novis_shards.py data/processed/novis
```

Then open `data/previews/index.html` and look at every scene.

## When planning, or writing up

**[`data_collection_protocol.md`](data_collection_protocol.md)** — the long
reference. Scene variety (§8), how many scenes and sessions (§7, §9), ethics
and consent (§10), the shard pipeline (§12, §13), training (§14), what to
report in the paper (§15), mistakes that cost a session (§16).

> Its §0.5 design decisions are **partly superseded**: D2 flipped from BAB to
> BAA on 24 Sept 2026, and D3 (two thermal channels) is deferred. The file
> carries banners wherever this matters. Where it disagrees with
> `session1_baa_capture.md` about which sensor the photo is framed to, the
> session document wins.

## When a sensor misbehaves

**[`hardware_log.md`](hardware_log.md)** — how the node was built and every
fix, with the reasoning. Wiring tables for both thermal sensors, the
initialise-sensors-before-WiFi finding, and the dead-pixel explanation.

**[`NOVIS_Final_Module_Build.md`](NOVIS_Final_Module_Build.md)** — assembly,
pass criteria per sensor, battery wiring, symptom → cause table.

## Historical

**[`NOVIS_Build_Guide.md`](NOVIS_Build_Guide.md)** — the original end-to-end
build guide. Part E5 still holds the consent-form wording. The rest is
superseded by the files above.

---

## Where things live

| Path | What | In git? |
|---|---|---|
| `data/real_capture/` | dashboard `.json` exports | no |
| `data/previews/` | per-scene photo + thermal + `index.html` | no |
| `data/processed/` | `.npz` training shards | no |
| `firmware/dashboard/` | the capture dashboard (`.ino` + `page_html.h`) | yes |
| `scripts/` | ingest, previews, prepare, check | yes |
| `docs/` | these documents | yes |

Everything under `data/` stays on D: and is git-ignored — capture files are
large (a full-size JPEG per scene, a 768-pixel thermal frame per sample).
