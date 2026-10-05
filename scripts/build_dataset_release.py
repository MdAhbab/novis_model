"""Build a self-contained, shareable NOVIS dataset folder from dashboard exports.

One command takes the raw .json exports (and, optionally, the phone-side .png
scene images) and writes a folder someone else can open without the repo:

    <out>/
      README.md            what this is, how it was captured, counts, caveats
      scenes.csv           one row per scene (from export_scene_previews.py)
      index.html           every scene on one page: photo | BAA | merged
      scenes/<id>/         photo.jpg, thermal_baa/bab/merged.png, pair.jpg
      raw/                 the .json exports exactly as downloaded
      phone_png/           the scene .png images saved on the phone, if given
      shards/train|val|stress/     .npz training shards (real samples only)
      shards/train_augmented/      label-preserving augmentations of TRAIN only

Augmentation is kept in its own folder and counted separately, never mixed
into train/ and never applied to val/ or stress/: an augmented copy of a
validation scene would let the model be scored on something it trained on.
The README states the real count and the augmented count apart.

Usage:
  python scripts/build_dataset_release.py ^
      --captures "data/real_capture/batch_2026-10/json/*.json" ^
      --phone-png "data/real_capture/batch_2026-10/png/*.png" ^
      --out data/NOVIS_dataset_v1 --held-out-scenes "Canteen1,..." --r-use 4.0
"""

import argparse
import csv
import glob
import json
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from make_standalone_viewer import make_standalone  # noqa: E402
from prepare_novis import load_captures  # noqa: E402


def run(cmd):
    print("\n$ " + " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    out = r.stdout + r.stderr
    print(out.strip()[-4000:])
    if r.returncode != 0:
        raise SystemExit(f"step failed: {cmd[1]}")
    return out


def refine_scene_table(path: Path, scenes: dict, split_of: dict,
                       imputed: list, names_file: Path) -> list:
    """Rewrite scenes.csv with readable names, codes and the split.

    The ids typed on the phone during capture ("Chess booard1",
    "Classroom 6(3rd)") stay in raw_scene_id, the key back to raw/ and to
    scenes/<id>/. Readable location/view/description come from
    scene_names.csv; an id missing there falls back to what was typed.
    Codes are numbered per location in capture order (CAN-01, GAR-03, ...).
    """
    names = {}
    if names_file.exists():
        with open(names_file, encoding="utf-8") as fh:
            names = {r["raw_scene_id"]: r for r in csv.DictReader(fh)}
    with open(path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    imputed_ids = {s for s, _ in imputed}

    def key(r):
        n = names.get(r["scene_id"], {})
        return (n.get("location") or r["room"],
                scenes[r["scene_id"]].get("capturedAt", ""))

    seq: Counter = Counter()
    out = []
    for r in sorted(rows, key=key):
        sid = r["scene_id"]
        n = names.get(sid, {})
        loc = n.get("location") or r["room"]
        seq[loc] += 1
        out.append({
            "scene_code": f"{loc[:3].upper()}-{seq[loc]:02d}",
            "location": loc,
            "view": n.get("view") or r["room"],
            "description": n.get("description") or r["note"],
            "distance_m": r["distance_m"],
            "distance_source": ("imputed" if sid in imputed_ids
                                else "measured" if r["distance_m"] else ""),
            "people": r["people"],
            "lighting": r["lighting"],
            "split": split_of.get(sid, "train"),
            "samples": r["samples"],
            "thermal_frames": r["baa_frames"],
            "baa_min_c": r["baa_lo_c"],
            "baa_max_c": r["baa_hi_c"],
            "bab_recorded": r["bab_recorded"],
            "photo_px": r["photo_px"],
            "captured": scenes[sid].get("capturedAt", "")[:16].replace("T", " "),
            "raw_scene_id": sid,
            "folder": f"scenes/{sid}",
        })
    # utf-8-sig so Excel opens it with the right encoding
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    return out


def augment_train(src: Path, dst: Path, copies: int, seed: int = 0) -> int:
    """Label-preserving augmentations of real TRAIN shards.

    Per real sample, `copies` variants, each one of:
      - horizontal flip: thermal, gray and ab flipped together, sonar left and
        right swapped (the two cones swap sides when the scene does). Echo is
        one mono microphone with no left/right content, so it is unchanged.
      - thermal sensor noise: Gaussian, sigma 0.01 of the [0,1] range
        (0.25 C under the default 15-40 C mapping), about the per-pixel noise
        measured on real frames.
      - thermal level shift: +/-0.02 (+/-0.5 C), the scale of the sensor-to-
        sensor and frame-to-frame offsets seen on real captures.
    The target photo is never altered except by the flip, which moves it
    together with every sensor so the pairing stays true.
    """
    rng = np.random.default_rng(seed)
    dst.mkdir(parents=True, exist_ok=True)
    n_out, shard = 0, 0
    for f in sorted(src.glob("*.npz")):
        d = dict(np.load(f))
        n = len(d["gray"])
        outs = {k: [] for k in d}
        for _ in range(copies):
            a = {k: v.copy() for k, v in d.items()}
            kind = rng.integers(0, 3, n)
            flip = kind == 0
            for k in ("thermal", "gray", "ab", "inv_depth", "depth_valid"):
                a[k][flip] = a[k][flip][..., ::-1]
            s = a["sonar"]
            s[flip, 0], s[flip, 1] = d["sonar"][flip, 1], d["sonar"][flip, 0]
            s[flip, 2], s[flip, 3] = d["sonar"][flip, 3], d["sonar"][flip, 2]
            noise = kind == 1
            a["thermal"][noise] += rng.normal(0, 0.01, a["thermal"][noise].shape).astype(np.float32)
            shift = kind == 2
            a["thermal"][shift] += rng.uniform(-0.02, 0.02, (shift.sum(), 1, 1, 1)).astype(np.float32)
            a["thermal"] = np.clip(a["thermal"], 0, 1)
            for k in outs:
                outs[k].append(a[k])
        np.savez_compressed(dst / f"shard_{shard:04d}.npz",
                            **{k: np.concatenate(v) for k, v in outs.items()})
        n_out += n * copies
        shard += 1
    return n_out


def impute_missing(raw_dir: Path, filled_dir: Path) -> list:
    """Copy the exports, filling scene fields that were left blank, flagged.

    Only fields that can be estimated from the scene's own sensor readings are
    filled: a missing "main surface distance" becomes the median sonar range
    of that scene's samples (the nearer cone, as the operator would have
    measured the surface straight ahead). Every filled field gets a sibling
    "<field>Imputed" saying how, so nothing downstream - or any reader - can
    mistake it for a measurement. raw/ itself is never modified.

    Not imputed, deliberately: echo where the node did not hear its own chirp
    (there is no signal to estimate it from, and an invented waveform would
    be indistinguishable from a real one in the shards), and people counts
    that disagree with the scene note (needs a human to decide which is right).
    """
    filled_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for f in sorted(raw_dir.glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for sid, sc in (doc.get("scenes") or {}).items():
            if sc.get("distanceM") is None:
                near = [min(v for v in (s.get("sonarLeftMm"), s.get("sonarRightMm")) if v)
                        for s in doc.get("samples", [])
                        if s.get("sceneId") == sid and (s.get("sonarLeftMm") or s.get("sonarRightMm"))]
                if near:
                    sc["distanceM"] = round(float(np.median(near)) / 1000, 2)
                    sc["distanceMImputed"] = "median sonar range of this scene's samples"
                    if (sid, sc["distanceM"]) not in done:
                        done.append((sid, sc["distanceM"]))
        (filled_dir / f.name).write_text(json.dumps(doc), encoding="utf-8")
    return done


def augment_scene_images(scenes_dir: Path, dst: Path, labels: dict,
                         seed: int = 0) -> list:
    """Two labelled variants of every real scene's pictures, for viewing.

    Variants are derived, not captured: "flip" mirrors the photo and every
    thermal image together, "light" changes the photo's brightness and
    contrast by up to +/-15% (a different exposure of the same view) and
    leaves thermal alone, since lighting does not change temperature. Every
    folder is named <code>__aug_<kind> and every pair image is stamped
    AUGMENTED so a variant cannot pass for a capture once copied elsewhere.
    `labels` maps a raw scene id to (code, view).
    """
    from PIL import Image, ImageDraw, ImageEnhance, ImageOps
    rng = np.random.default_rng(seed)
    dst.mkdir(parents=True, exist_ok=True)
    made = []
    for sd in sorted(p for p in scenes_dir.iterdir() if p.is_dir()):
        code, view = labels.get(sd.name, (sd.name, ""))
        for kind in ("flip", "light"):
            od = dst / f"{code}__aug_{kind}"
            od.mkdir(exist_ok=True)
            for name in ("photo.jpg", "thermal_baa.png", "thermal_bab.png", "thermal_merged.png"):
                src = sd / name
                if not src.exists():
                    continue
                im = Image.open(src).convert("RGB")
                if kind == "flip":
                    im = ImageOps.mirror(im)
                elif name == "photo.jpg":
                    im = ImageEnhance.Brightness(im).enhance(float(rng.uniform(0.85, 1.15)))
                    im = ImageEnhance.Contrast(im).enhance(float(rng.uniform(0.85, 1.15)))
                im.save(od / name, quality=92)
            ph, th = od / "photo.jpg", od / "thermal_merged.png"
            if not th.exists():
                th = od / "thermal_baa.png"
            if ph.exists() and th.exists():
                a = Image.open(ph); b = Image.open(th).resize((round(a.height * 4 / 3), a.height))
                pair = Image.new("RGB", (a.width + b.width + 6, a.height + 28), (16, 18, 24))
                pair.paste(a, (0, 28)); pair.paste(b, (a.width + 6, 28))
                ImageDraw.Draw(pair).text((8, 8), f"AUGMENTED ({kind}) - derived from real scene "
                                          f"{code} ({view}), not a new capture", fill=(255, 180, 84))
                pair.save(od / "pair.jpg", quality=92)
            made.append((sd.name, kind, od.name))
    made.sort(key=lambda m: m[2])
    rows = "\n".join(f'<div class="s"><div class="h"><b>{o}</b> <span>from {labels.get(s, (s,))[0]} · {k}</span></div>'
                     f'<img src="augmented_scenes/{o}/pair.jpg" loading="lazy"></div>' for s, k, o in made)
    (dst.parent / "index_augmented.html").write_text(f"""<!doctype html><meta charset="utf-8">
<title>NOVIS - augmented scene images</title>
<style>body{{background:#0d0f14;color:#dee2eb;font:14px system-ui;margin:0;padding:24px}}
.s{{border:1px solid #3a2f1d;border-radius:10px;margin-bottom:18px;overflow:hidden;background:#15120c}}
.h{{padding:10px 14px}} .h span{{color:#c9a46a}} img{{display:block;width:100%}}
.banner{{background:#3a2a10;color:#ffcf8a;padding:12px 16px;border-radius:8px;margin-bottom:20px}}</style>
<h1>Augmented scene images</h1>
<div class="banner"><b>Not new captures.</b> Every image here is derived from one of the
real scenes in index.html - flipped, or re-exposed. Count the dataset by the real
scenes only.</div>
{rows}""", encoding="utf-8")
    return made


def write_release_index(path: Path, rows: list, aug: list, st: dict):
    """The dataset's front page: counts, a scene table, then every scene.

    Each scene shows its photo and the three thermal views as separate,
    labelled images, and its augmented variants folded underneath it, marked
    as derived so they are seen next to, never mistaken for, the capture.
    """
    from html import escape as e
    aug_by = {}
    for sid, kind, folder in aug:
        aug_by.setdefault(sid, []).append((kind, folder))
    locs = sorted({r["location"] for r in rows})
    split_note = {"train": "train", "val": "val (held out)", "stress": f"stress (&gt;{st['r_use']:g} m)"}

    overview = "\n".join(
        f'<tr data-loc="{e(r["location"])}"><td><a href="#{r["scene_code"]}">{r["scene_code"]}</a></td>'
        f'<td>{e(r["location"])}</td><td>{e(r["view"])}</td><td>{e(r["description"])}</td>'
        f'<td class="r">{r["distance_m"] or "—"}{"*" if r["distance_source"] == "imputed" else ""}</td>'
        f'<td class="r">{r["people"]}</td><td>{r["lighting"]}</td>'
        f'<td class="r">{r["samples"]}</td><td><span class="b {r["split"]}">{r["split"]}</span></td></tr>'
        for r in rows)

    cards = []
    for r in rows:
        d = "scenes/" + e(r["raw_scene_id"])
        imgs = [("photo.jpg", "Photo (target)"), ("thermal_baa.png", "Thermal BAA · wide"),
                ("thermal_bab.png", "Thermal BAB · narrow"), ("thermal_merged.png", "Thermal merged")]
        figs = "".join(f'<figure><img src="{d}/{f}" loading="lazy" alt="{e(r["scene_code"])} {c}">'
                       f'<figcaption>{c}</figcaption></figure>' for f, c in imgs)
        variants = aug_by.get(r["raw_scene_id"], [])
        aug_html = ""
        if variants:
            aug_html = (f'<details><summary>Augmented variants ({len(variants)}) — derived from this '
                        f'scene, not new captures</summary><div class="aug">'
                        + "".join(f'<figure><img src="augmented_scenes/{e(o)}/pair.jpg" loading="lazy" '
                                  f'alt="augmented {k}"><figcaption>AUGMENTED · {k}</figcaption></figure>'
                                  for k, o in variants)
                        + "</div></details>")
        dist = (f'{r["distance_m"]} m' + (' (imputed)' if r["distance_source"] == "imputed" else '')
                if r["distance_m"] else "no distance")
        cards.append(
            f'<section class="s" id="{r["scene_code"]}" data-loc="{e(r["location"])}">'
            f'<div class="h"><b>{r["scene_code"]}</b><span class="t">{e(r["location"])} · {e(r["view"])}</span>'
            f'<span class="b {r["split"]}">{split_note[r["split"]]}</span></div>'
            f'<div class="d">{e(r["description"])}</div>'
            f'<div class="m"><span>{dist}</span>'
            f'<span>{r["people"]} {"person" if r["people"] == "1" else "people"}</span>'
            f'<span>{r["lighting"]}</span><span>{r["samples"]} samples</span>'
            f'<span>BAA {r["baa_min_c"]}–{r["baa_max_c"]} °C</span><span>{r["captured"]}</span>'
            f'<span class="raw">raw id: {e(r["raw_scene_id"])}</span></div>'
            f'<div class="g">{figs}</div>{aug_html}</section>')

    buttons = '<button class="on" data-f="">All</button>' + "".join(
        f'<button data-f="{e(l)}">{e(l)} ({sum(r["location"] == l for r in rows)})</button>' for l in locs)

    path.write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NOVIS dataset v1</title>
<style>
:root{{--bg:#0d0f14;--card:#12151c;--line:#232735;--fg:#dee2eb;--mute:#8b93a7;--acc:#7cc4ff;
  --train:#2d6a4f;--val:#7c5cbf;--stress:#a8572a;--aug:#ffcf8a}}
*{{box-sizing:border-box}}
body{{background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif;margin:0;padding:24px 16px;
  max-width:1280px;margin:auto}}
h1{{font-size:24px;margin:0 0 2px}} h2{{font-size:17px;margin:32px 0 10px}}
.sub{{color:var(--mute);margin-bottom:18px}}
a{{color:var(--acc)}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px}}
.stat{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}}
.stat b{{display:block;font-size:22px}} .stat span{{color:var(--mute);font-size:12px}}
.stat.aug{{border-color:#5a4520}} .stat.aug b{{color:var(--aug)}}
.links a{{margin-right:16px}}
.tw{{overflow-x:auto;border:1px solid var(--line);border-radius:10px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
td:nth-child(4){{white-space:normal;min-width:220px}}
th{{background:var(--card);color:var(--mute);font-weight:600}} .r{{text-align:right}}
.b{{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;color:#fff}}
.b.train{{background:var(--train)}} .b.val{{background:var(--val)}} .b.stress{{background:var(--stress)}}
.filters{{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 14px}}
button{{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:99px;
  padding:5px 12px;font:inherit;cursor:pointer}} button.on{{background:var(--acc);color:#0d0f14;border-color:var(--acc)}}
.s{{border:1px solid var(--line);border-radius:12px;margin-bottom:18px;background:var(--card);overflow:hidden;
  scroll-margin-top:12px}}
.h{{display:flex;gap:12px;flex-wrap:wrap;align-items:center;padding:10px 14px 0}}
.h b{{font-size:17px}} .h .t{{font-size:15px}}
.d{{padding:4px 14px 0}}
.m{{display:flex;flex-wrap:wrap;gap:4px 14px;padding:4px 14px 10px;color:var(--mute);font-size:12.5px}}
.m .raw{{font-family:ui-monospace,monospace}}
.g{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 6px 6px}}
figure{{margin:0;background:#000;border-radius:6px;overflow:hidden}}
figure img{{display:block;width:100%;aspect-ratio:4/3;object-fit:contain}}
figcaption{{font-size:12px;color:var(--mute);padding:4px 8px;background:var(--card)}}
details{{border-top:1px solid #3a2f1d;background:#15120c}}
summary{{cursor:pointer;padding:8px 14px;color:var(--aug)}}
.aug{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:0 6px 6px}}
.aug img{{aspect-ratio:auto}} .aug figcaption{{color:var(--aug);background:#15120c}}
@media (max-width:760px){{.g{{grid-template-columns:repeat(2,minmax(0,1fr))}} .aug{{grid-template-columns:minmax(0,1fr)}}}}
</style></head><body>
<h1>NOVIS real-capture dataset — v1</h1>
<div class="sub">Camera-free scene sensing: two thermal cameras, two ultrasonic rangers and an acoustic echo,
each scene paired with a phone photo of the same view. Captured {e(st['days'])}.</div>
<div class="stats">
<div class="stat"><b>{st['scenes']}</b><span>real scenes (one photo each)</span></div>
<div class="stat"><b>{st['samples']}</b><span>real sensor samples</span></div>
<div class="stat"><b>{st['train']} / {st['val']} / {st['stress']}</b><span>train / val / stress samples</span></div>
<div class="stat aug"><b>{len(aug)}</b><span>augmented scene images — derived, not captured</span></div>
<div class="stat aug"><b>{st['aug_samples']}</b><span>augmented train samples — derived, not captured</span></div>
</div>
<div class="links"><a href="README.md">README</a><a href="scenes.csv">scenes.csv</a>
<a href="index_augmented.html">All augmented images</a><a href="check_report.txt">Data check report</a></div>
<p class="sub">Val = {e(st['val_label'])}, a location never seen in training. Stress = scenes beyond
{st['r_use']:g} m, the sonar's range. Augmented data is shown separately and is not counted as scenes or samples.</p>

<h2>Scenes</h2>
<div class="filters">{buttons}</div>
<div class="tw"><table><thead><tr><th>Code</th><th>Location</th><th>View</th><th>Description</th>
<th class="r">Dist (m)</th><th class="r">People</th><th>Light</th><th class="r">Samples</th><th>Split</th></tr></thead>
<tbody>{overview}</tbody></table></div>
<p class="sub">* distance not entered at capture; filled from the scene's median sonar range.</p>

<h2>Every scene</h2>
{''.join(cards)}
<script>
document.querySelectorAll('.filters button').forEach(b => b.onclick = () => {{
  document.querySelectorAll('.filters button').forEach(x => x.classList.toggle('on', x === b));
  const f = b.dataset.f;
  document.querySelectorAll('[data-loc]').forEach(el => el.hidden = !!f && el.dataset.loc !== f);
}});
</script>
</body></html>
""", encoding="utf-8")


def count_npz(d: Path) -> int:
    return sum(len(np.load(f)["gray"]) for f in d.glob("*.npz")) if d.exists() else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", nargs="+", required=True)
    ap.add_argument("--phone-png", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--held-out-scenes", required=True)
    ap.add_argument("--held-out-label", default="")
    ap.add_argument("--r-use", type=float, default=4.0)
    ap.add_argument("--aug-copies", type=int, default=3)
    args = ap.parse_args()

    out = Path(args.out)
    # Clear the contents, not the folder itself: on Windows a folder open in
    # Explorer cannot be removed, and rmtree would leave it half-deleted.
    if out.exists():
        for child in out.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    (out / "raw").mkdir(parents=True)

    files = sorted({p for g in args.captures for p in glob.glob(g)})
    for f in files:
        shutil.copy2(f, out / "raw" / Path(f).name)
    pngs = sorted({p for g in args.phone_png for p in glob.glob(g)})
    if pngs:
        (out / "phone_png").mkdir()
        for f in pngs:
            shutil.copy2(f, out / "phone_png" / Path(f).name)

    py = sys.executable
    imputed = impute_missing(out / "raw", out / "raw_filled")
    raw_glob = str(out / "raw_filled" / "*.json")
    run([py, HERE / "export_scene_previews.py", "--captures", raw_glob,
         "--out", out / "scenes"])
    # The preview page names scenes by their typed ids; the release gets its
    # own index.html (written below) that uses the refined names.
    (out / "scenes" / "index.html").unlink()
    shutil.move(str(out / "scenes" / "scenes.csv"), out / "scenes.csv")

    prep = run([py, HERE / "prepare_novis.py", "--captures", raw_glob,
                "--out", out / "shards", "--r-use", args.r_use,
                "--held-out-scenes", args.held_out_scenes])
    check = run([py, HERE / "check_novis_shards.py", out / "shards",
                 "--stress", out / "shards" / "stress"])

    # ---- numbers for the README, taken from the data, not typed in ----
    scenes, samples = load_captures([raw_glob])
    per = Counter(s["sceneId"] for s in samples)
    held = {s.strip() for s in args.held_out_scenes.split(",") if s.strip()}
    stress = sorted(sid for sid, sc in scenes.items()
                    if sc.get("distanceM") is not None and sc["distanceM"] > args.r_use)
    n_tr, n_va, n_st = (count_npz(out / "shards" / k) for k in ("train", "val", "stress"))
    echo_line = next((l for l in prep.splitlines() if l.startswith("echo:")), "echo: n/a")
    notes = [l.strip() for l in prep.splitlines()
             if l.strip().startswith(("BAA:", "BAB:")) and "recorded on" not in l]
    renames = [l.strip()[len("NOTE: "):] for l in prep.splitlines()
               if l.strip().startswith("NOTE: scene id")]
    days = sorted({sc.get("capturedAt", "")[:10] for sc in scenes.values()})
    ppl = Counter(min(int(sc.get("people") or 0), 3) for sc in scenes.values())
    light = Counter(sc.get("lighting", "?") for sc in scenes.values())
    missing_d = sorted(sid for sid, sc in scenes.items() if sc.get("distanceM") is None)
    disagree = sorted(sid for sid, sc in scenes.items()
                      if (sc.get("people") or 0) == 0
                      and any(w in (sc.get("note") or "").lower() for w in ("human", "person"))
                      and "no human" not in (sc.get("note") or "").lower())

    split_of = {sid: "val" if sid in held else "stress" if sid in stress else "train"
                for sid in scenes}
    rows = refine_scene_table(out / "scenes.csv", scenes, split_of, imputed,
                              HERE / "scene_names.csv")
    labels = {r["raw_scene_id"]: (r["scene_code"], r["view"]) for r in rows}
    aug_scenes = augment_scene_images(out / "scenes", out / "augmented_scenes", labels)
    n_aug = augment_train(out / "shards" / "train",
                          out / "shards" / "train_augmented", args.aug_copies)
    write_release_index(out / "index.html", rows, aug_scenes, {
        "scenes": len(scenes), "samples": len(samples),
        "train": n_tr, "val": n_va, "stress": n_st, "aug_samples": n_aug,
        "val_label": args.held_out_label or ", ".join(sorted(held)),
        "r_use": args.r_use, "days": ", ".join(days)})
    table = "\n".join(
        f"| {r['scene_code']} | {r['location']} | {r['view']} | {r['description']} | "
        f"{r['distance_m'] or '—'} | {r['people']} | {r['lighting']} | "
        f"{r['samples']} | {r['split']} | `{r['raw_scene_id']}` |"
        for r in rows)

    readme = f"""# NOVIS real-capture dataset — v1

Camera-free scene sensing: a thermal camera pair, two ultrasonic rangers and an
acoustic echo, each paired with a phone photo of the same view as the target.
Built {date.today().isoformat()} from {len(files)} dashboard exports captured on
{', '.join(days)}.

## At a glance

| | |
|---|---|
| Scenes (distinct views, each with one photo) | **{len(scenes)}** |
| Real sensor samples | **{len(samples)}** (≈25 per scene) |
| Split — train / val / stress | {n_tr} / {n_va} / {n_st} samples |
| Augmented training samples (separate, see below) | {n_aug} |
| Augmented scene images (separate, see below) | {len(aug_scenes)} from {len(scenes)} real scenes |
| People in view — 0 / 1 / 2 / 3+ | {ppl[0]} / {ppl[1]} / {ppl[2]} / {ppl[3]} scenes |
| Lighting | {', '.join(f'{k} {v}' for k, v in sorted(light.items()))} |

Open **`index.html`** to see every scene: the photo, what the wide thermal
sensor (BAA) saw, and the merged view of both thermal sensors.

## What one sample is

Every scene has one photo (512×384, the training target). The sensor node takes
about 25 readings of the still scene, each holding:

- **Thermal BAA** — MLX90640, 32×24 px, wide field (~110°×75°). The capture sensor;
  photos are framed to its view.
- **Thermal BAB** — MLX90640, 32×24 px, narrower field: about the central
  0.62×0.48 of BAA's view at twice the detail. Recorded on every sample.
- **Sonar** — two HC-SR04, left and right, millimetres, 4 m maximum.
- **Echo** — 960 samples (60 ms at 16 kHz) from one microphone after a 5 ms
  1→8 kHz chirp from the node's own speaker.

## Folders

| Folder | Contents |
|---|---|
| `raw/` | The `.json` exports exactly as downloaded — the source of truth |
| `raw_filled/` | Same exports with blank scene fields filled in, each marked `<field>Imputed` — what everything below was built from |
| `augmented_scenes/`, `index_augmented.html` | Flipped / re-exposed variants of the real scene images, labelled AUGMENTED |
| `phone_png/` | Scene images saved on the phone during capture ({len(pngs)}) |
| `scenes/<id>/` | `photo.jpg`, `thermal_baa.png`, `thermal_bab.png`, `thermal_merged.png`, `pair.jpg` |
| `scenes.csv` | One row per scene: code, location, view, description, split, and the raw id |
| `shards/train`, `val`, `stress` | `.npz` training arrays, real samples only |
| `shards/train_augmented` | Augmented copies of **train only** |

## Split

- **val = one whole location never seen in training: {args.held_out_label or ', '.join(sorted(held))}.**
  A per-scene split would put other views of the same room on both sides and
  score recognition of a known room, not generalisation.
- **stress = scenes beyond {args.r_use:g} m** (the sonar's limit): {', '.join(stress) or 'none'}.
  Kept out of train/val and reported separately.
- Everything else is train.

## Augmentation — stated separately on purpose

`shards/train_augmented/` holds {args.aug_copies} label-preserving variants of every
**train** sample: a horizontal flip of every sensor and the photo together
(sonar left/right swapped to match), thermal sensor noise (σ ≈ 0.25 °C), or a
thermal level shift (±0.5 °C) — all on the scale of noise measured on the real
frames. They are **not new scenes**: report results on real data, and count
this dataset as {len(scenes)} scenes / {len(samples)} samples. Val and stress are
never augmented.

## Processing applied to the shards (raw `.json` is untouched)

- Thermal frames un-mirrored (the sensors deliver them flipped left–right).
- Chess sub-page offset of the MLX90640 cancelled per frame.
- Dead and biased pixels corrected from their neighbours:
{chr(10).join('  - ' + n for n in notes)}
- {echo_line}. Samples where the node did not hear its own chirp are marked
  echo-missing (`mask[1] = 0`) rather than fed in as noise.
- No depth sensor: depth arrays are zero and masked out.

## Known limits and data notes

- **Thermal sees heat, not furniture.** A room at rest is one temperature; the
  thermal image shows people and warm objects, not walls or chairs. Room
  geometry has to come from sonar and echo.
- Sonar gives two ranges (two narrow cones), not a depth image.
- Distance left blank at capture, filled from the scene's median sonar range (marked `distanceMImputed`): {', '.join(f'{s} = {d} m' for s, d in imputed) or 'none'}.
- Not filled in, on purpose: echo where the node did not hear its own chirp (no signal to estimate from — marked missing instead), and people counts that disagree with the scene note.
- People count 0 but the note mentions a person: {', '.join(disagree) or 'none'} — check.
- A scene id typed twice for two different places is kept apart automatically
  (renamed `<id> @HH-MM`): {'; '.join(renames) or 'none in this release'}.

## Scenes

Codes are numbered per location in capture order. `raw_scene_id` is the id
typed during capture, which names the folder under `scenes/` and the scene in `raw/`.

| Code | Location | View | Description | Distance (m) | People | Lighting | Samples | Split | Raw id |
|---|---|---|---|---|---|---|---|---|---|
{table}
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    (out / "check_report.txt").write_text(check, encoding="utf-8")

    # One file with every picture embedded, for sending on its own.
    make_standalone(out)

    # A light copy for showing and sharing: everything a person looks at, no
    # training arrays (the shards are most of the size and need the repo).
    view = out.parent / (out.name + "_view.zip")
    with zipfile.ZipFile(view, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.rglob("*")):
            if p.is_file() and "shards" not in p.relative_to(out).parts:
                z.write(p, Path(out.name) / p.relative_to(out))
    print(f"\ndataset written to {out}")
    print(f"view-only zip (no shards): {view}  {view.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
