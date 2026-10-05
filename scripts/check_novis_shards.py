"""Check that prepared NOVIS shards are actually trainable before you train.

Run this straight after scripts/prepare_novis.py. It is a five-second read of
the whole prepared set that answers the questions a training run will not:
are the shapes and ranges what the model expects, is any input channel dead
(a thermal sensor that never varied, an echo that never returned, sonar that
always timed out), how many distinct ground-truth photos are behind all these
samples, and - the one that silently ruins a result - does the same scene
appear in both train and val?

  python scripts/check_novis_shards.py data/processed/novis

Pass a single folder that contains train/ and val/, or point --train and --val
at shard folders directly.

Exit code is 1 if anything that would make the run meaningless was found, so
this can sit in front of training in a script.
"""

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np

EXPECT = {
    "thermal": (1, 24, 32),
    "echo": (2, 64, 64),
    "sonar": (10,),
    "mask": (3,),
    "gray": (1, 192, 256),
    "ab": (2, 192, 256),
    "inv_depth": (1, 192, 256),
    "depth_valid": (1, 192, 256),
}

problems: list = []
notes: list = []


def fail(msg):
    problems.append(msg)


def warn(msg):
    notes.append(msg)


def load_split(shard_dir: Path):
    """Return {key: stacked array} for every shard in a folder, or None."""
    files = sorted(shard_dir.glob("*.npz"))
    if not files:
        return None, 0
    parts = {k: [] for k in EXPECT}
    for f in files:
        with np.load(f) as z:
            missing = set(EXPECT) - set(z.files)
            if missing:
                fail(f"{f.name}: missing arrays {sorted(missing)}")
                continue
            for k in EXPECT:
                parts[k].append(z[k])
    return {k: np.concatenate(v) for k, v in parts.items() if v}, len(files)


def photo_ids(gray: np.ndarray) -> list:
    """One id per sample, hashed from its target image.

    Every sample in a scene shares that scene's photo, so identical hashes
    mean 'same scene' without needing the scene ids to still be around.
    """
    return [hashlib.sha1(np.ascontiguousarray(g)).hexdigest() for g in gray]


def describe(name: str, data: dict, n_files: int):
    n = data["gray"].shape[0]
    print(f"\n=== {name}: {n} samples in {n_files} shard file(s) ===")

    for k, shape in EXPECT.items():
        a = data[k]
        if a.shape[1:] != shape:
            fail(f"{name}/{k}: shape {a.shape[1:]}, expected {shape}")
        if a.dtype != np.float32:
            warn(f"{name}/{k}: dtype {a.dtype}, expected float32")
        if not np.isfinite(a).all():
            fail(f"{name}/{k}: contains NaN or inf")
        print(f"  {k:12s} {str(a.shape):22s} "
              f"min {a.min():7.3f}  max {a.max():7.3f}  mean {a.mean():7.3f}")

    # --- ranges the model and the losses assume ---
    for k, lo, hi in [("thermal", 0.0, 1.0), ("echo", 0.0, 1.0),
                      ("gray", 0.0, 1.0), ("ab", -1.0, 1.0)]:
        a = data[k]
        if a.min() < lo - 1e-4 or a.max() > hi + 1e-4:
            fail(f"{name}/{k}: values outside [{lo}, {hi}]")

    if not np.allclose(data["mask"], 1.0):
        warn(f"{name}: mask is not all ones - some samples are missing a "
             f"modality (expected [1,1,1] for real node captures)")

    # --- dead input channels: the failure that trains happily and predicts nothing ---
    t = data["thermal"]
    per_frame_spread = float(np.mean(t.max(axis=(1, 2, 3)) - t.min(axis=(1, 2, 3))))
    if per_frame_spread < 0.02:
        fail(f"{name}: thermal frames are nearly flat (mean spread "
             f"{per_frame_spread:.4f}) - the sensor saw no structure at all")
    elif per_frame_spread < 0.08:
        warn(f"{name}: thermal frames have little contrast (mean spread "
             f"{per_frame_spread:.3f}) - with --thermal-norm fixed this is "
             f"normal for rooms with nothing warm in them; compare against a "
             f"perframe build before reading anything into it")

    e = data["echo"]
    dead_echo = int(np.sum(e.reshape(len(e), -1).max(axis=1) <= 1e-6))
    if dead_echo:
        fail(f"{name}: {dead_echo}/{n} samples have an all-zero echo "
             f"spectrogram")

    valid = data["sonar"][:, 2:4]
    none_valid = int(np.sum(valid.sum(axis=1) == 0))
    print(f"  sonar: {n - none_valid}/{n} samples have at least one valid "
          f"range ({100.0 * none_valid / max(n, 1):.1f}% blind)")
    if none_valid > 0.5 * n and name.startswith("stress"):
        # The stress split is, by construction, scenes past --r-use, which is
        # normally set to the HC-SR04's own 4 m limit - sonar going blind
        # there is the expected reason those scenes are in it, not a fault.
        warn(f"{name}: {100.0 * none_valid / n:.0f}% of samples have no valid "
             f"sonar range - expected past the sonar's reach")
    elif none_valid > 0.5 * n:
        fail(f"{name}: over half the samples have no valid sonar range - "
             f"check the sensors, not the model")
    elif none_valid > 0.2 * n:
        warn(f"{name}: {100.0 * none_valid / n:.0f}% of samples have no "
             f"valid sonar range")

    if float(data["depth_valid"].max()) > 0:
        warn(f"{name}: depth_valid is not all zero - the node has no depth "
             f"sensor, so real captures should leave depth unsupervised")

    # --- how much of this is genuinely distinct ---
    ids = photo_ids(data["gray"])
    uniq = sorted(set(ids))
    counts = {u: ids.count(u) for u in uniq}
    lo_id = min(counts, key=counts.get)
    hi_id = max(counts, key=counts.get)
    print(f"  scenes (distinct target photos): {len(uniq)}  "
          f"samples per scene: min {counts[lo_id]}, max {counts[hi_id]}, "
          f"mean {n / max(len(uniq), 1):.1f}")
    if len(uniq) < 5:
        warn(f"{name}: only {len(uniq)} distinct scenes - metrics from this "
             f"are noise, not a result")
    return set(uniq), n, len(uniq)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default="data/processed/novis",
                    help="folder holding train/ and val/")
    ap.add_argument("--train", default=None)
    ap.add_argument("--val", default=None)
    ap.add_argument("--stress", default=None,
                    help="also check the out-of-operating-range split "
                         "produced by prepare_novis.py --r-use (default: "
                         "<root>/stress if it exists). It gets the same "
                         "shape/dead-channel checks as train/val, but is "
                         "never leak-checked against them - one scene lands "
                         "in exactly one split by construction (its distance "
                         "puts it there), so overlap cannot occur.")
    args = ap.parse_args()

    root = Path(args.root)
    train_dir = Path(args.train) if args.train else root / "train"
    val_dir = Path(args.val) if args.val else root / "val"
    stress_dir = Path(args.stress) if args.stress else root / "stress"

    train, n_tf = load_split(train_dir)
    val, n_vf = load_split(val_dir)
    if train is None:
        raise SystemExit(f"no .npz shards in {train_dir}")

    tr_ids, n_tr, s_tr = describe("train", train, n_tf)
    if val is None:
        fail(f"no .npz shards in {val_dir} - nothing to validate on; capture "
             f"more scenes or name val scenes with --held-out-scenes")
        va_ids, n_va, s_va = set(), 0, 0
    else:
        va_ids, n_va, s_va = describe("val", val, n_vf)

    # --- the leak check: same scene on both sides of the split ---
    overlap = tr_ids & va_ids
    print(f"\n=== split ===")
    print(f"  train {n_tr} samples / {s_tr} scenes"
          f"    val {n_va} samples / {s_va} scenes")
    if overlap:
        fail(f"{len(overlap)} scene(s) appear in BOTH train and val - the "
             f"validation score would be meaningless. Re-run "
             f"prepare_novis.py; it splits by scene, so this means two scene "
             f"ids share one photo (an id typed twice, or a scene captured "
             f"in two sessions under different ids).")
    else:
        print("  no scene appears on both sides - split is clean")
    if s_va and s_va < 0.1 * (s_tr + s_va):
        warn(f"val holds only {s_va} of {s_tr + s_va} scenes; 15-20% is the "
             f"usual target")

    if stress_dir.exists():
        stress, n_sf = load_split(stress_dir)
        if stress is not None:
            describe("stress (beyond r_use)", stress, n_sf)
            print("  (not leak-checked against train/val - a scene's "
                  "distance places it in exactly one split)")

    print()
    for w in notes:
        print(f"NOTE:    {w}")
    for p in problems:
        print(f"PROBLEM: {p}")
    if problems:
        print(f"\n{len(problems)} problem(s) found - fix these before training.")
        return 1
    print("Shards look trainable"
          + (f" ({len(notes)} note(s) above)" if notes else "") + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
