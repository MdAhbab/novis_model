"""Smoke test: model builds, shapes are right, and it learns.

Run from NOVIS_Model:  python tests/test_smoke.py
(Also pytest-compatible.) CPU-only friendly; finishes in a few minutes.
Uses debug-scale dims; the full-size model differs only in width/depth.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import torch  # noqa: E402

from novis.data import SyntheticNOVISDataset, collate_batch  # noqa: E402
from novis.losses import total_loss  # noqa: E402
from novis.models import (NOVISNet, PatchDiscriminator,  # noqa: E402
                          d_hinge_loss, g_hinge_loss)

OUT_HW = (96, 128)


def build(color_head=True):
    torch.manual_seed(0)
    return NOVISNet(dim=96, depth=3, heads=4, decoder_chs=(96, 64, 48),
                    ffn_ratio=2, drop_path=0.1, color_head=color_head)


def _batch(n=2):
    ds = SyntheticNOVISDataset(n=n, out_hw=OUT_HW)
    return collate_batch([ds[i] for i in range(n)])


def test_forward_shapes():
    model = build()
    batch = _batch()
    with torch.no_grad():
        out = model(batch["thermal"], batch["echo"], batch["sonar"],
                    batch["mask"])
    h, w = OUT_HW
    assert out["gray"].shape == (2, 1, h, w), out["gray"].shape
    assert out["inv_depth"].shape == (2, 1, h, w)
    assert out["ab"].shape == (2, 2, h, w)
    assert out["log_var"].shape == (2, 1, h, w)
    assert float(out["gray"].min()) >= 0.0 and float(out["gray"].max()) <= 1.0
    print("forward shapes ok, params: %.2fM" % (model.param_count() / 1e6))


def test_full_size_variant():
    """The paper model: dim 320, depth 14, 4 decoder stages -> 192x256."""
    torch.manual_seed(0)
    model = NOVISNet(dim=320, depth=14, heads=8, ffn_ratio=4,
                     decoder_chs=(320, 224, 160, 112))
    assert model.out_hw == (192, 256)
    batch = _batch(1)
    with torch.no_grad():
        out = model(batch["thermal"], batch["echo"], batch["sonar"],
                    batch["mask"])
    assert out["gray"].shape == (1, 1, 192, 256)
    print("full-size variant ok, params: %.2fM" % (model.param_count() / 1e6))


def test_color_head_optional():
    model = build(color_head=False)
    batch = _batch()
    with torch.no_grad():
        out = model(batch["thermal"], batch["echo"], batch["sonar"],
                    batch["mask"])
    assert "ab" not in out and "log_var" not in out
    losses = total_loss(out, batch)
    assert torch.isfinite(losses["total"])
    print("color-head-off path ok")


def test_missing_modalities():
    model = build()
    batch = _batch()
    for m in range(3):
        mask = torch.ones(2, 3)
        mask[:, m] = 0.0
        out = model(batch["thermal"], batch["echo"], batch["sonar"], mask)
        assert torch.isfinite(out["gray"]).all()
    print("missing-modality paths ok")


def test_discriminator():
    disc = PatchDiscriminator()
    gray = torch.rand(2, 1, *OUT_HW)
    cond = torch.rand(2, 1, *OUT_HW)
    logits = disc(gray, cond)
    assert logits.ndim == 4 and torch.isfinite(logits).all()
    d = d_hinge_loss(logits, disc(torch.rand(2, 1, *OUT_HW), cond))
    g = g_hinge_loss(logits)
    assert torch.isfinite(d) and torch.isfinite(g)
    print("discriminator ok, params: %.2fM"
          % (sum(p.numel() for p in disc.parameters()) / 1e6))


def test_overfit_small():
    model = build()
    ds = SyntheticNOVISDataset(n=4, out_hw=OUT_HW)
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
    test_full_size_variant()
    test_color_head_optional()
    test_missing_modalities()
    test_discriminator()
    test_overfit_small()
    print("ALL SMOKE TESTS PASSED")
