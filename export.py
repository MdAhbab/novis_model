"""Export a trained NOVISNet to ONNX (opset 17) for phone deployment.

Example:
  python export.py --config configs/fusion_full.yaml ^
                   --ckpt checkpoints/fusion_full/best.pt ^
                   --out results/novisnet.onnx
"""

import argparse
import sys
from pathlib import Path

# Windows consoles default to cp1252; torch's exporter prints unicode marks.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import torch  # noqa: E402

from novis.config import load_config  # noqa: E402
from novis.models import build_model  # noqa: E402


class ExportWrapper(torch.nn.Module):
    """Tuple outputs for ONNX (dict outputs are not portable)."""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, thermal, echo, sonar, mask):
        out = self.model(thermal, echo, sonar, mask)
        return out["gray"], out["inv_depth"], out["ab"], out["log_var"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", default="results/novisnet.onnx")
    args = ap.parse_args()

    cfg = load_config(args.config)
    model = build_model(cfg)
    state = torch.load(args.ckpt, map_location="cpu", weights_only=True)
    model.load_state_dict(state["model"])
    wrapper = ExportWrapper(model)
    wrapper.eval()

    # Batch is fixed at 1: the phone runs one frame at a time.
    dummy = (torch.zeros(1, 1, 24, 32), torch.zeros(1, 2, 64, 64),
             torch.zeros(1, 10), torch.ones(1, 3))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        wrapper, dummy, args.out, opset_version=18,
        input_names=["thermal", "echo", "sonar", "mask"],
        output_names=["gray", "inv_depth", "ab", "log_var"])
    print(f"exported: {args.out}")

    try:
        import onnxruntime as ort
        import numpy as np
        sess = ort.InferenceSession(args.out)
        outs = sess.run(None, {
            "thermal": np.zeros((1, 1, 24, 32), np.float32),
            "echo": np.zeros((1, 2, 64, 64), np.float32),
            "sonar": np.zeros((1, 10), np.float32),
            "mask": np.ones((1, 3), np.float32)})
        print("onnxruntime check ok:", [o.shape for o in outs])
    except ImportError:
        print("onnxruntime not installed; skipped runtime check "
              "(pip install onnxruntime to enable).")


if __name__ == "__main__":
    main()
