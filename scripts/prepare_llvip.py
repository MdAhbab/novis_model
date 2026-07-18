"""Convert LLVIP (or any aligned infrared/visible pair tree) into NOVIS shards.

Expected input layout (LLVIP official release):
  <root>/infrared/train/*.jpg   <root>/visible/train/*.jpg
  <root>/infrared/test/*.jpg    <root>/visible/test/*.jpg

Output: data/processed/llvip/{train,val}/shard_####.npz

Usage:
  python scripts/prepare_llvip.py --root path/to/LLVIP --out data/processed/llvip
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novis.data import degradation as D  # noqa: E402

OUT_H, OUT_W = 192, 256      # must match data.out_hw in the training config
SHARD = 512


def load_pair(ir_path: Path, vis_path: Path):
    ir = np.asarray(Image.open(ir_path).convert("L"), dtype=np.float32) / 255.0
    vis = np.asarray(Image.open(vis_path).convert("RGB"))
    return ir, vis


def center_crop_aspect(img: np.ndarray, aspect: float):
    """Crop to the target aspect (w/h) around the center."""
    h, w = img.shape[:2]
    if w / h > aspect:
        nw = int(h * aspect)
        x0 = (w - nw) // 2
        return img[:, x0: x0 + nw]
    nh = int(w / aspect)
    y0 = (h - nh) // 2
    return img[y0: y0 + nh]


def resize(img: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    mode = "RGB" if img.ndim == 3 else "F"
    pil = Image.fromarray(img if img.ndim == 3 else img.astype(np.float32),
                          mode=mode)
    r = pil.resize((out_w, out_h), Image.BILINEAR)
    return np.asarray(r, dtype=np.float32 if img.ndim == 2 else np.uint8)


def process_split(ir_dir: Path, vis_dir: Path, out_dir: Path, rng):
    out_dir.mkdir(parents=True, exist_ok=True)
    ir_files = sorted(ir_dir.glob("*.jpg")) + sorted(ir_dir.glob("*.png"))
    buf = {k: [] for k in ["thermal", "echo", "sonar", "mask", "gray", "ab",
                           "inv_depth", "depth_valid"]}
    shard_i = 0

    def flush():
        nonlocal shard_i
        if not buf["gray"]:
            return
        np.savez_compressed(out_dir / f"shard_{shard_i:04d}.npz",
                            **{k: np.stack(v) for k, v in buf.items()})
        for v in buf.values():
            v.clear()
        shard_i += 1

    n_done, n_skip = 0, 0
    for irf in ir_files:
        visf = vis_dir / irf.name
        if not visf.exists():
            n_skip += 1
            continue
        ir, vis = load_pair(irf, visf)
        # Match the MLX90640 55x35 degree FOV aspect (approx 1.57).
        ir = center_crop_aspect(ir, aspect=OUT_W / OUT_H)
        vis = center_crop_aspect(vis, aspect=OUT_W / OUT_H)
        ir_hi = resize(ir, OUT_H, OUT_W)
        vis = resize(vis, OUT_H, OUT_W)

        thermal = D.degrade_thermal(ir_hi, rng)
        gray, ab = D.lab_targets(vis)

        buf["thermal"].append(thermal[None].astype(np.float32))
        buf["echo"].append(np.zeros((2, 64, 64), np.float32))
        buf["sonar"].append(np.zeros(10, np.float32))
        buf["mask"].append(np.array([1, 0, 0], np.float32))   # thermal only
        buf["gray"].append(gray[None])
        buf["ab"].append(ab.transpose(2, 0, 1))
        buf["inv_depth"].append(np.zeros((1, OUT_H, OUT_W), np.float32))
        buf["depth_valid"].append(np.zeros((1, OUT_H, OUT_W), np.float32))
        n_done += 1
        if len(buf["gray"]) >= SHARD:
            flush()
    flush()
    print(f"{out_dir}: {n_done} pairs -> {shard_i} shards ({n_skip} skipped)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="LLVIP root folder")
    ap.add_argument("--out", default="data/processed/llvip")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    root, out = Path(args.root), Path(args.out)
    process_split(root / "infrared" / "train", root / "visible" / "train",
                  out / "train", rng)
    process_split(root / "infrared" / "test", root / "visible" / "test",
                  out / "val", rng)


if __name__ == "__main__":
    main()
