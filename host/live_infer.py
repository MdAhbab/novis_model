"""Run NOVISNet on assembled frames and (optionally) display the outputs.

As a library:  load_model(cfg, ckpt) -> model; infer(model, assembler) -> dict.
As a script (offline synthetic demo, no hardware or BLE needed):

  python -m host.live_infer --config configs/fusion_full.yaml \
      --ckpt checkpoints/fusion_full/best.pt --source synthetic

If --ckpt is omitted, a randomly initialized model is used so the pipeline can
still be exercised (outputs will not be meaningful).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import torch

from novis.config import load_config
from novis.data import degradation as D
from novis.models import build_model

from . import protocol as P
from .assemble import FrameAssembler


def load_model(config: str, ckpt: str | None, device: str = "cpu"):
    cfg = load_config(config)
    model = build_model(cfg)
    if ckpt:
        state = torch.load(ckpt, map_location=device, weights_only=True)
        model.load_state_dict(state["model"])
        del state
    model.to(device).eval()
    return model


@torch.no_grad()
def infer(model, assembler: FrameAssembler) -> dict:
    x = assembler.model_input()
    out = model(x["thermal"], x["echo"], x["sonar"], x["mask"])
    result = {k: v[0].cpu().numpy() for k, v in out.items()}
    # Convert normalized inverse depth back to meters for display.
    result["depth_m"] = D.inv01_to_depth(result["inv_depth"][0])
    return result


def synthetic_frames(n_cycles: int = 1):
    """Yield encoded plaintext frames like the firmware stub produces."""
    import struct
    seq = {P.THERMAL: 0, P.ECHO: 0, P.SONAR: 0}
    for _ in range(n_cycles):
        therm = np.full((24, 32), 2000, dtype="<i2")
        therm[11:16, :] += 800
        yield P.build_frame(P.THERMAL, seq[P.THERMAL], 0, therm.tobytes())
        seq[P.THERMAL] += 1
        pcm = np.zeros(P.ECHO_SAMPLES, dtype="<i2")
        pcm[200:230] = 8000
        yield P.build_frame(P.ECHO, seq[P.ECHO], 0, pcm.tobytes())
        seq[P.ECHO] += 1
        son = struct.pack("<HHBBBB", 1500, 2200, 0x03, 0, 0, 0)
        yield P.build_frame(P.SONAR, seq[P.SONAR], 0, son)
        seq[P.SONAR] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/fusion_full.yaml")
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--source", choices=["synthetic", "ble"],
                    default="synthetic")
    ap.add_argument("--save", default="results/live_output.npz")
    args = ap.parse_args()

    model = load_model(args.config, args.ckpt)

    if args.source == "ble":
        from .receiver import run_ble
        run_ble(model)
        return

    asm = FrameAssembler()
    for frame_bytes in synthetic_frames(1):
        asm.update(P.parse_frame(frame_bytes))
    out = infer(model, asm)
    Path(args.save).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.save, **out)
    print("inference ok; output shapes:")
    for k, v in out.items():
        print(f"  {k:10s} {tuple(v.shape)}")
    print(f"saved: {args.save}")


if __name__ == "__main__":
    main()
