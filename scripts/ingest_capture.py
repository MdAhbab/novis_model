"""Move dashboard exports out of Downloads and into the project, on D:.

The dashboard downloads to wherever the browser puts things, which on this
laptop is C: - the drive that keeps filling up. Capture files are large (every
sample carries a 768-pixel thermal frame and every scene a full-size JPEG), so
they belong on D: with the rest of the project.

Run this after every session:

    python scripts/ingest_capture.py

It finds novis_dataset_*.json and novis_summary_*.csv in your Downloads
folder, checks each one actually parses and has scenes in it, and MOVES it to
data/real_capture/ (which .gitignore already excludes, so nothing this size
ever reaches git).

Nothing is overwritten. A file whose name is already taken gets a numeric
suffix, and a file that is byte-identical to one already stored is reported
and left alone rather than duplicated.

  --from DIR     look somewhere else (default: your Downloads folder)
  --out DIR      land somewhere else (default: data/real_capture)
  --session NAME put them in a named subfolder, e.g. --session session01
  --copy         copy instead of moving, if you want Downloads left intact
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

PATTERNS = ("novis_dataset_*.json", "novis_summary_*.csv")


def digest(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def describe(p: Path) -> str:
    """A capture file is worth nothing without scenes - say so before moving."""
    if p.suffix.lower() != ".json":
        return "summary csv"
    try:
        with open(p, encoding="utf-8") as fh:
            doc = json.load(fh)
    except Exception as e:
        return f"UNREADABLE ({type(e).__name__})"
    n_sc = len(doc.get("scenes") or {})
    n_sa = len(doc.get("samples") or [])
    with_photo = sum(1 for s in (doc.get("scenes") or {}).values()
                     if str(s.get("photo", "")).startswith("data:image"))
    if not n_sc:
        return f"{n_sa} samples but NO SCENES - nothing to train against"
    return f"{n_sc} scenes ({with_photo} with photos), {n_sa} samples"


def unique(dest: Path) -> Path:
    if not dest.exists():
        return dest
    for i in range(2, 1000):
        cand = dest.with_name(f"{dest.stem}_{i}{dest.suffix}")
        if not cand.exists():
            return cand
    raise SystemExit(f"too many name collisions for {dest.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default=None,
                    help="folder to take files from (default: ~/Downloads)")
    ap.add_argument("--out", default="data/real_capture")
    ap.add_argument("--session", default=None,
                    help="put them in this subfolder, e.g. session01")
    ap.add_argument("--copy", action="store_true",
                    help="copy rather than move")
    args = ap.parse_args()

    src = Path(args.src) if args.src else Path.home() / "Downloads"
    if not src.is_dir():
        raise SystemExit(f"no such folder: {src}")
    out = Path(args.out)
    if args.session:
        out = out / args.session
    out.mkdir(parents=True, exist_ok=True)

    found = sorted({p for pat in PATTERNS for p in src.glob(pat)})
    if not found:
        print(f"nothing to ingest in {src}")
        print(f"  looked for: {', '.join(PATTERNS)}")
        return

    existing = {digest(p): p for p in out.rglob("*")
                if p.is_file() and p.suffix.lower() in (".json", ".csv")}

    moved = skipped = 0
    total = 0
    for p in found:
        info = describe(p)
        if info.startswith("UNREADABLE"):
            print(f"  SKIP  {p.name}  {info}")
            skipped += 1
            continue
        d = digest(p)
        if d in existing:
            print(f"  dup   {p.name}  identical to {existing[d].name} - left "
                  f"in {src.name}")
            skipped += 1
            continue
        dest = unique(out / p.name)
        if args.copy:
            shutil.copy2(p, dest)
        else:
            shutil.move(str(p), str(dest))
        existing[d] = dest
        size = dest.stat().st_size
        total += size
        moved += 1
        print(f"  {'copied' if args.copy else 'moved '} {dest.name}  "
              f"{size / 1e6:.1f} MB  {info}")

    print(f"\n{moved} file(s) -> {out}   ({total / 1e6:.1f} MB)"
          + (f", {skipped} skipped" if skipped else ""))
    if moved:
        print("\nnext:")
        print(f'  python scripts/export_scene_previews.py --captures "{out}/*.json"')
        print("  # then open data/previews/index.html and check every scene")


if __name__ == "__main__":
    sys.exit(main())
