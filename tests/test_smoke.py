"""Smoke test: model builds, shapes are right, and it learns.

Run from NOVIS_Model:  python tests/test_smoke.py
(Also pytest-compatible.) CPU-only friendly; finishes in a few minutes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import torch  # noqa: E402

from novis.data import SyntheticNOVISDataset, collate_batch  # noqa: E402
from novis.losses import total_loss  # noqa: E402
from novis.models import NOVISNet  # noqa: E402


def build():
    torch.manual_seed(0)
    return NOVISNet(dim=128, depth=6, heads=4, decoder_chs=(96, 64, 48))


def test_forward_shapes():
    model = build()
    ds = SyntheticNOVISDataset(n=2)
    batch = collate_batch([ds[0], ds[1]])
    with torch.no_grad():
        out = model(batch["thermal"], batch["echo"], batch["sonar"],
                    batch["mask"])
    assert out["gray"].shape == (2, 1, 96, 128), out["gray"].shape
    assert out["inv_depth"].shape == (2, 1, 96, 128)
    assert out["ab"].shape == (2, 2, 96, 128)
    assert out["log_var"].shape == (2, 1, 96, 128)
    assert float(out["gray"].min()) >= 0.0 and float(out["gray"].max()) <= 1.0
    print("forward shapes ok, params: %.2fM" % (model.param_count() / 1e6))


def test_missing_modalities():
    model = build()
    ds = SyntheticNOVISDataset(n=2)
    batch = collate_batch([ds[0], ds[1]])
    for m in range(3):
        mask = torch.ones(2, 3)
        mask[:, m] = 0.0
        out = model(batch["thermal"], batch["echo"], batch["sonar"], mask)
        assert torch.isfinite(out["gray"]).all()
    print("missing-modality paths ok")


def test_overfit_small():
    model = build()
    ds = SyntheticNOVISDataset(n=4)
    batch = collate_batch([ds[i] for i in range(4)])
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    first, last = None, None
    for step in range(30):
        out = model(batch["thermal"], batch["echo"], batch["sonar"],
                    batch["mask"])
        losses = total_loss(out, batch)
        opt.zero_grad(set_to_none=True)
        losses["total"].backward()
        opt.step()
        v = float(losses["total"].detach())
        if first is None:
            first = v
        last = v
    print(f"overfit: loss {first:.4f} -> {last:.4f}")
    assert last < first * 0.8, f"loss did not drop enough: {first} -> {last}"


if __name__ == "__main__":
    test_forward_shapes()
    test_missing_modalities()
    test_overfit_small()
    print("ALL SMOKE TESTS PASSED")
