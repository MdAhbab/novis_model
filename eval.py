"""Evaluate a checkpoint and write results/metrics.json plus a sample grid PNG.

Example:
  python eval.py --config configs/fusion_full.yaml ^
                 --ckpt checkpoints/fusion_full/best.pt --data synthetic
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from novis.config import load_config  # noqa: E402
from novis.data import NOVISShardDataset, SyntheticNOVISDataset  # noqa: E402
from novis.engine import Trainer, make_loader  # noqa: E402
from novis.models import build_model  # noqa: E402


def save_sample_grid(model, ds, device, out_png, n=6):
    """Rows: thermal (upsampled), predicted gray, target gray, pred inv-depth,
    target inv-depth."""
    from PIL import Image
    from novis.data import collate_batch
    model.eval()
    batch = collate_batch([ds[i] for i in range(min(n, len(ds)))])
    batch = {k: v.to(device) for k, v in batch.items()}
    with torch.no_grad():
        out = model(batch["thermal"], batch["echo"], batch["sonar"],
                    batch["mask"])
    H, W = batch["gray"].shape[-2:]
    rows = []
    thermal_up = torch.nn.functional.interpolate(
        batch["thermal"], size=(H, W), mode="nearest")
    for row in (thermal_up, out["gray"], batch["gray"], out["inv_depth"],
                batch["inv_depth"]):
        imgs = [row[i, 0].float().cpu().numpy() for i in range(row.shape[0])]
        rows.append(np.concatenate(imgs, axis=1))
    grid = (np.clip(np.concatenate(rows, axis=0), 0, 1) * 255).astype(np.uint8)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(grid).save(out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--data", choices=["synthetic", "shards"], default="shards")
    ap.add_argument("--val-shards", default=None)
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")

    if args.data == "synthetic":
        val_ds = SyntheticNOVISDataset(n=cfg.data.synthetic_val_n,
                                       out_hw=tuple(cfg.data.out_hw))
    else:
        if not args.val_shards:
            ap.error("--data shards requires --val-shards")
        val_ds = NOVISShardDataset(args.val_shards)

    model = build_model(cfg)
    state = torch.load(args.ckpt, map_location=device, weights_only=True)
    model.load_state_dict(state["model"])
    del state
    model.to(device)

    trainer = Trainer(model, cfg, run_dir="results/_evaltmp", device=device)
    metrics = trainer.validate(
        make_loader(val_ds, cfg.train.batch_size, False, cfg.train.workers))

    root = Path(__file__).resolve().parent
    out_json = root / "results" / "metrics.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"checkpoint": args.ckpt, "metrics": metrics}, f, indent=2)
    save_sample_grid(model, val_ds, device,
                     root / "results" / "samples" / "eval_grid.png")
    print(json.dumps(metrics, indent=2))
    print(f"written: {out_json}")


if __name__ == "__main__":
    main()
