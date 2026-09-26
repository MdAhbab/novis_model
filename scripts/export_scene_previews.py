"""Turn dashboard captures into pictures you can actually look at.

The photos are ALREADY inside the .json exports, as base64 data URIs - nothing
was lost by not downloading them separately. This script unpacks them back into
real files, next to a rendered thermal image and the scene's readings, so a
whole session can be checked by eye in a couple of minutes instead of trusting
that it went well.

What it writes, per scene, under --out:

    <scene id>/photo.jpg        the ground-truth photo, exactly as captured
    <scene id>/thermal_baa.png  BAA averaged over the scene, dashboard colours
    <scene id>/thermal_bab.png  BAB, same (only if BAB was recorded)
    <scene id>/pair.jpg         photo | thermal side by side, with the readings

    index.html                  every scene on one scrollable page
    scenes.csv                  one row per scene, for a spreadsheet

The side-by-side is the one that matters. **Framing errors are invisible in the
numbers and obvious in that image**: if the photo shows a chair BAA never saw,
or the warm body sits at a different place in each half, this is where it shows.
Check it the same evening, while the room can still be re-shot.

Light on purpose - numpy and Pillow only, no torch, no GPU. Runs on a laptop.

Usage:
  python scripts/export_scene_previews.py --captures "data/real_capture/*.json"
  python scripts/export_scene_previews.py --captures "data/real_capture/*.json" ^
      --out data/previews/session01 --scale 12
"""

import argparse
import base64
import csv
import glob
import html
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_novis import (THERMAL_H, THERMAL_W,  # noqa: E402
                           dead_pixel_mask, load_captures,
                           remove_subpage_offset, repair_dead)

# The dashboard's own colour ramp, copied from firmware/dashboard/page_html.h.
# Kept identical on purpose: a preview that does not look like what you saw on
# the phone in the room is a preview you cannot compare against your memory.
RAW = False   # set from --no-repair

STOPS = [(0.00, 8, 5, 30), (0.15, 44, 17, 96), (0.30, 87, 21, 126),
         (0.45, 138, 34, 106), (0.60, 186, 54, 85), (0.75, 224, 92, 47),
         (0.88, 248, 149, 64), (1.00, 252, 255, 164)]


def ramp(t: np.ndarray) -> np.ndarray:
    """(H,W) in [0,1] -> (H,W,3) uint8, piecewise-linear through STOPS."""
    t = np.clip(t, 0.0, 1.0)
    pos = np.array([s[0] for s in STOPS])
    cols = np.array([s[1:] for s in STOPS], dtype=np.float32)
    out = np.empty(t.shape + (3,), np.float32)
    for c in range(3):
        out[..., c] = np.interp(t, pos, cols[:, c])
    return out.astype(np.uint8)


def percentile_bounds(a: np.ndarray, frac: float = 0.01):
    """1st/99th percentile, matching the dashboard's dead-pixel-proof scaling."""
    lo, hi = np.percentile(a, [frac * 100, 100 - frac * 100])
    if hi - lo < 0.1:
        hi = lo + 0.1
    return float(lo), float(hi)


def thermal_png(centi_c: np.ndarray, scale: int) -> tuple:
    """(24,32) centi-C -> a PIL image at `scale`x, plus the range it used."""
    t = centi_c.astype(np.float32) / 100.0
    lo, hi = percentile_bounds(t)
    rgb = ramp((t - lo) / (hi - lo))
    img = Image.fromarray(rgb, "RGB")
    img = img.resize((THERMAL_W * scale, THERMAL_H * scale), Image.BICUBIC)
    return img, lo, hi


def decode_photo_full(data_uri: str) -> Image.Image:
    """The scene photo at its original size - not the 256x192 the model gets."""
    return Image.open(io.BytesIO(base64.b64decode(data_uri.split(",", 1)[1])))


def caption(img: Image.Image, lines, pad: int = 8) -> Image.Image:
    """Stick a dark caption bar under an image."""
    d0 = ImageDraw.Draw(img)
    lh = d0.textbbox((0, 0), "Ag")[3] + 3
    bar = lh * len(lines) + pad * 2
    out = Image.new("RGB", (img.width, img.height + bar), (16, 18, 24))
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    for i, line in enumerate(lines):
        d.text((pad, img.height + pad + i * lh), line, fill=(222, 226, 235))
    return out


def scene_samples(samples, sid):
    return [s for s in samples if s.get("sceneId") == sid]


def mean_thermal(rows, key, okkey):
    """Average a scene's frames. Averaging 25 samples of a still scene kills
    most of the per-frame sensor noise, so what is left is the scene itself."""
    frames = [np.asarray(s[key], dtype=np.float32).reshape(THERMAL_H, THERMAL_W)
              for s in rows if s.get(key) is not None and s.get(okkey, True)]
    if not RAW:
        frames = [remove_subpage_offset(f) for f in frames]
    if not frames:
        return None, []
    return np.mean(frames, axis=0), frames


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", nargs="+", required=True,
                    help="glob(s) for dashboard .json exports")
    ap.add_argument("--out", default="data/previews")
    ap.add_argument("--scale", type=int, default=12,
                    help="pixels per thermal pixel (24x32 -> 288x384 at 12)")
    ap.add_argument("--photo-width", type=int, default=520,
                    help="width the photo is scaled to in pair.jpg")
    ap.add_argument("--no-repair", action="store_true",
                    help="show raw frames: dead pixels and the chess "
                         "sub-page offset both left in")
    args = ap.parse_args()
    global RAW
    RAW = args.no_repair

    # The same loader prepare_novis.py uses, so the previews are built from
    # exactly the samples that will become training data - including its
    # de-duplication of overlapping downloads.
    scenes, samples = load_captures(args.captures)
    if not scenes:
        raise SystemExit("no scenes in those files - nothing to preview")

    # Dead-pixel masks over the whole run, same rule prepare_novis.py uses, so
    # the preview shows what the model will be trained on rather than something
    # prettier or uglier than the truth.
    masks = {}
    if not args.no_repair:
        for key, okkey in (("thermal", "thermalOk"), ("thermalFar", "thermalFarOk")):
            fr = [remove_subpage_offset(np.asarray(s[key]).reshape(THERMAL_H, THERMAL_W))
                  for s in samples
                  if s.get(key) is not None and s.get(okkey, True)]
            masks[key] = dead_pixel_mask(fr, 5.0, 0.9)
            n = int(masks[key].sum())
            if fr and n:
                at = ", ".join(f"({x},{y})" for y, x in zip(*np.where(masks[key])))
                print(f"{'BAA' if key == 'thermal' else 'BAB'}: "
                      f"{n} dead pixel(s) at {at} - repaired in these previews")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows_csv, cards = [], []

    for sid in sorted(scenes):
        sc = scenes[sid]
        rows = scene_samples(samples, sid)
        d = out / sid
        d.mkdir(parents=True, exist_ok=True)

        photo = decode_photo_full(sc["photo"])
        photo.convert("RGB").save(d / "photo.jpg", quality=92)

        panels, lo_hi = [], {}
        for key, okkey, label in (("thermal", "thermalOk", "baa"),
                                  ("thermalFar", "thermalFarOk", "bab")):
            avg, frames = mean_thermal(rows, key, okkey)
            if avg is None:
                continue
            if not args.no_repair and masks.get(key) is not None:
                avg = repair_dead(avg, masks[key])
            if not RAW:
                avg = avg[:, ::-1]      # sensor frames are mirrored against the photo
            img, lo, hi = thermal_png(avg, args.scale)
            img.save(d / f"thermal_{label}.png")
            lo_hi[label] = (lo, hi, len(frames))
            if label == "baa":
                panels.append(img)

        # pair.jpg - photo beside BAA, the one image that exposes a framing slip
        if panels:
            th = panels[0]
            pw = args.photo_width
            ph = max(1, round(photo.height * pw / photo.width))
            left = photo.convert("RGB").resize((pw, ph), Image.LANCZOS)
            sc_h = max(left.height, th.height)
            tw = max(1, round(th.width * sc_h / th.height))
            right = th.resize((tw, sc_h), Image.NEAREST)
            left = left.resize((max(1, round(left.width * sc_h / left.height)),
                                sc_h), Image.LANCZOS)
            pair = Image.new("RGB", (left.width + right.width + 6, sc_h),
                             (16, 18, 24))
            pair.paste(left, (0, 0))
            pair.paste(right, (left.width + 6, 0))

            son = [(s.get("sonarLeftMm"), s.get("sonarRightMm")) for s in rows]
            sl = [a for a, _ in son if a]
            sr = [b for _, b in son if b]
            lo, hi, n = lo_hi.get("baa", (0, 0, 0))
            pair = caption(pair, [
                f"{sid}   {sc.get('room','?')}   "
                f"{sc.get('distanceM','?')} m   "
                f"{sc.get('people',0)} people   {sc.get('lighting','?')}",
                f"BAA {lo:.1f}-{hi:.1f} C over {n} frames   "
                f"sonar L {int(np.mean(sl)) if sl else 0} mm / "
                f"R {int(np.mean(sr)) if sr else 0} mm",
                f"note: {sc.get('note','') or '-'}",
            ])
            pair.save(d / "pair.jpg", quality=92)
            cards.append((sid, sc, lo_hi, len(rows)))

        lo, hi, n = lo_hi.get("baa", (None, None, 0))
        rows_csv.append({
            "scene_id": sid, "room": sc.get("room", ""),
            "distance_m": sc.get("distanceM", ""),
            "people": sc.get("people", ""), "lighting": sc.get("lighting", ""),
            "note": sc.get("note", ""), "samples": len(rows),
            "baa_frames": n,
            "baa_lo_c": f"{lo:.2f}" if lo is not None else "",
            "baa_hi_c": f"{hi:.2f}" if hi is not None else "",
            "bab_recorded": "yes" if "bab" in lo_hi else "no",
            "photo_px": f"{photo.width}x{photo.height}",
        })
        print(f"  {sid:28s} {len(rows):3d} samples  "
              f"photo {photo.width}x{photo.height}")

    with open(out / "scenes.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows_csv[0]))
        w.writeheader()
        w.writerows(rows_csv)

    _write_index(out, cards, rows_csv)
    print(f"\n{len(scenes)} scenes -> {out}")
    print(f"open {out / 'index.html'} and scroll: photo on the left, BAA on "
          f"the right. They should show the same room, framed the same way.")


def _write_index(out: Path, cards, rows_csv):
    by_id = {r["scene_id"]: r for r in rows_csv}
    parts = ["""<!doctype html><meta charset="utf-8">
<title>NOVIS scene previews</title>
<style>
 body{background:#0d0f14;color:#dee2eb;font:14px/1.5 system-ui,sans-serif;
      margin:0;padding:24px}
 h1{font-size:20px;margin:0 0 4px} .sub{color:#8b93a7;margin-bottom:24px}
 .s{border:1px solid #232735;border-radius:10px;margin-bottom:18px;
    overflow:hidden;background:#12151c}
 .h{display:flex;gap:14px;flex-wrap:wrap;align-items:baseline;
    padding:10px 14px;border-bottom:1px solid #232735}
 .h b{font-size:15px} .h span{color:#8b93a7;font-size:13px}
 .n{color:#c8cede;font-size:13px;padding:8px 14px 0}
 img{display:block;width:100%;height:auto}
 .warn{color:#ffb454}
</style>
<h1>NOVIS scene previews</h1>
<div class="sub">Left = the photo the model must reproduce. Right = what BAA
actually saw. Same room, same framing, warm things in the same place &mdash;
if not, re-shoot that scene.</div>"""]
    for sid, sc, lo_hi, nsamp in cards:
        r = by_id[sid]
        warn = ""
        if not sc.get("distanceM"):
            warn = ' <span class="warn">no distance recorded</span>'
        parts.append(
            f'<div class="s"><div class="h"><b>{html.escape(sid)}</b>'
            f'<span>{html.escape(str(sc.get("room","?")))}</span>'
            f'<span>{html.escape(str(sc.get("distanceM","?")))} m</span>'
            f'<span>{html.escape(str(sc.get("people",0)))} people</span>'
            f'<span>{html.escape(str(sc.get("lighting","?")))}</span>'
            f'<span>{nsamp} samples</span>'
            f'<span>BAA {r["baa_lo_c"]}&ndash;{r["baa_hi_c"]} &deg;C</span>'
            f'{warn}</div>'
            + (f'<div class="n">{html.escape(sc.get("note",""))}</div>'
               if sc.get("note") else "")
            + f'<img src="{html.escape(sid)}/pair.jpg" loading="lazy"></div>')
    (out / "index.html").write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
