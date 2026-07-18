"""Train NOVISNet.

Examples (from the NOVIS_Model folder):
  python train.py --config configs/debug_tiny.yaml --data synthetic
  python train.py --config configs/thermal_llvip.yaml --data shards ^
                  --train-shards data/processed/llvip/train ^
                  --val-shards   data/processed/llvip/val
  python train.py --config configs/fusion_full.yaml --data shards ^
                  --train-shards data/processed/all/train ^
                  --val-shards   data/processed/all/val ^
                  --init-from checkpoints/thermal_llvip/best.pt
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
    ap.add_argument("--resume", default=None,
                    help="latest.pt to continue an interrupted run")
    ap.add_argument("--init-from", default=None,
                    help="checkpoint whose weights seed this run "
                         "(stage A/B -> stage C)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.epochs is not None:
        cfg.train.epochs = args.epochs
    out_hw = tuple(cfg.data.out_hw)

    if args.data == "synthetic":
        train_ds = SyntheticNOVISDataset(
            n=cfg.data.synthetic_train_n,
            modality_dropout=cfg.train.modality_dropout, out_hw=out_hw)
        val_ds = SyntheticNOVISDataset(n=cfg.data.synthetic_val_n,
                                       out_hw=out_hw)
    else:
        if not (args.train_shards and args.val_shards):
            ap.error("--data shards requires --train-shards and --val-shards")
        train_ds = NOVISShardDataset(args.train_shards)
        val_ds = NOVISShardDataset(args.val_shards)
        if train_ds.out_hw != out_hw:
            ap.error(f"shards are {train_ds.out_hw} but data.out_hw is "
                     f"{out_hw}; re-run the prepare script or fix the config")

    model = build_model(cfg)
    if model.out_hw != out_hw:
        ap.error(f"decoder produces {model.out_hw} but data.out_hw is "
                 f"{out_hw}; decoder_chs and out_hw must agree")
    if args.init_from:
        state = torch.load(args.init_from, map_location="cpu",
                           weights_only=True)
        missing, unexpected = model.load_state_dict(state["model"],
                                                    strict=False)
        print(f"initialized from {args.init_from} "
              f"(missing {len(missing)}, unexpected {len(unexpected)})")

    n_params = model.param_count()
    print(f"NOVISNet parameters: {n_params / 1e6:.2f} M")
    print(f"device: {args.device or ('cuda' if torch.cuda.is_available() else 'cpu')}")
    if torch.cuda.is_available():
        print(f"gpu: {torch.cuda.get_device_name(0)}")

    run_name = args.run_name or Path(args.config).stem
    run_dir = Path(__file__).resolve().parent / "checkpoints" / run_name
    trainer = Trainer(model, cfg, run_dir=str(run_dir), device=args.device)
    if args.resume:
        trainer.load_checkpoint(args.resume)
    trainer.fit(train_ds, val_ds)
    print(f"done. checkpoints in {run_dir}")


if __name__ == "__main__":
    main()
