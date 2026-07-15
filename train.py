"""Train NOVISNet.

Examples (from the NOVIS_Model folder):
  python train.py --config configs/fusion_full.yaml --data synthetic
  python train.py --config configs/thermal_llvip.yaml --data shards ^
                  --train-shards data/processed/llvip/train ^
                  --val-shards   data/processed/llvip/val
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import torch  # noqa: E402

from novis.config import load_config  # noqa: E402
from novis.data import NOVISShardDataset, SyntheticNOVISDataset  # noqa: E402
from novis.engine import Trainer  # noqa: E402
from novis.models import build_model  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--data", choices=["synthetic", "shards"], default="shards")
    ap.add_argument("--train-shards", default=None)
    ap.add_argument("--val-shards", default=None)
    ap.add_argument("--run-name", default=None)
    ap.add_argument("--device", default=None)
    ap.add_argument("--epochs", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.epochs is not None:
        cfg.train.epochs = args.epochs

    if args.data == "synthetic":
        train_ds = SyntheticNOVISDataset(
            n=cfg.data.synthetic_train_n,
            modality_dropout=cfg.train.modality_dropout)
        val_ds = SyntheticNOVISDataset(n=cfg.data.synthetic_val_n)
    else:
        if not (args.train_shards and args.val_shards):
            ap.error("--data shards requires --train-shards and --val-shards")
        train_ds = NOVISShardDataset(args.train_shards)
        val_ds = NOVISShardDataset(args.val_shards)

    model = build_model(cfg)
    n_params = model.param_count()
    print(f"NOVISNet parameters: {n_params / 1e6:.2f} M")
    print(f"device: {args.device or ('cuda' if torch.cuda.is_available() else 'cpu')}")
    if torch.cuda.is_available():
        print(f"gpu: {torch.cuda.get_device_name(0)}")

    run_name = args.run_name or Path(args.config).stem
    run_dir = Path(__file__).resolve().parent / "checkpoints" / run_name
    trainer = Trainer(model, cfg, run_dir=str(run_dir), device=args.device)
    trainer.fit(train_ds, val_ds)
    print(f"done. checkpoints in {run_dir}")


if __name__ == "__main__":
    main()
