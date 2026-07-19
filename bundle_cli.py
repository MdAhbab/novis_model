"""Bundle CLI: package or load a portable NOVIS model bundle.

Export the current best checkpoint to a zip file that can be copied to a
USB drive and loaded on another machine without cloning the repository:

  python bundle_cli.py --config configs/fusion_full.yaml \
      --ckpt checkpoints/fusion_full/best.pt --out novis_bundle.zip

Load a bundle and start the server:

  python bundle_cli.py --load novis_bundle.zip --serve

Load a bundle and run a single inference (no server):

  python bundle_cli.py --load novis_bundle.zip --check
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))


def main():
    ap = argparse.ArgumentParser(
        description="Package or load a portable NOVIS model bundle.")
    sub = ap.add_subparsers(dest="command")

    # --- export ---
    exp = sub.add_parser("export", help="Create a bundle zip from a checkpoint")
    exp.add_argument("--config", required=True,
                     help="Config path (e.g. configs/fusion_full.yaml)")
    exp.add_argument("--ckpt", required=True,
                     help="Checkpoint path (e.g. checkpoints/.../best.pt)")
    exp.add_argument("--out", default="novis_bundle.zip",
                     help="Output zip path (default: novis_bundle.zip)")

    # --- load ---
    ld = sub.add_parser("load", help="Load a bundle and optionally serve")
    ld.add_argument("bundle", help="Path to the bundle zip file")
    ld.add_argument("--serve", action="store_true",
                    help="Start the server after loading")
    ld.add_argument("--port", type=int, default=8000)
    ld.add_argument("--check", action="store_true",
                    help="Run a single inference check and exit")

    args = ap.parse_args()

    if args.command == "export":
        from novis.server.service import InferenceService
        from novis.server.bundle import create_bundle
        svc = InferenceService(config=args.config, ckpt=args.ckpt)
        out = create_bundle(svc, Path(args.out))
        print(f"bundle created: {out} ({out.stat().st_size / 1e6:.1f} MB)")

    elif args.command == "load":
        from novis.server.bundle import load_bundle
        bundle_dir = Path(args.bundle).with_suffix("") / "_extracted"
        config_path, ckpt_path = load_bundle(Path(args.bundle), bundle_dir)

        if args.check:
            import numpy as np
            from novis.server.service import InferenceService
            svc = InferenceService(
                config=str(config_path), ckpt=str(ckpt_path))
            sample = svc.demo_sample(seed=42)
            result = svc.infer(sample)
            print(f"inference ok: latency {result['latency_ms']:.1f} ms, "
                  f"depth {result['depth_min_m']:.2f}-{result['depth_max_m']:.2f} m")
            return

        if args.serve:
            import os
            os.environ["NOVIS_CONFIG"] = str(config_path)
            os.environ["NOVIS_CKPT"] = str(ckpt_path)
            import uvicorn
            print(f"serving from bundle on :{args.port}")
            uvicorn.run("novis.server.app:app", host="127.0.0.1",
                        port=args.port, log_level="info")
            return

        print(f"extracted to {bundle_dir}")
        print(f"  config: {config_path}")
        print(f"  weights: {ckpt_path}")
        print("use --serve to start the server, or --check for a quick test")

    else:
        ap.print_help()


if __name__ == "__main__":
    main()
