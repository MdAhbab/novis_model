"""Evaluation metrics (methodology Section 5.4)."""

import torch

from .losses import ssim


@torch.no_grad()
def psnr(pred: torch.Tensor, target: torch.Tensor) -> float:
    mse = torch.mean((pred - target) ** 2).clamp_min(1e-10)
    return float(10.0 * torch.log10(1.0 / mse))


@torch.no_grad()
def depth_metrics(pred_inv: torch.Tensor, target_inv: torch.Tensor,
                  valid: torch.Tensor, dmin: float = 0.3,
                  dmax: float = 8.0) -> dict:
    lo, hi = 1.0 / dmax, 1.0 / dmin
    pd = 1.0 / (pred_inv * (hi - lo) + lo)
    td = 1.0 / (target_inv * (hi - lo) + lo)
    m = valid > 0.5
    if m.sum() == 0:
        return {"rmse_m": float("nan"), "delta1": float("nan")}
    pd, td = pd[m], td[m]
    rmse = float(torch.sqrt(torch.mean((pd - td) ** 2)))
    ratio = torch.maximum(pd / td, td / pd)
    delta1 = float((ratio < 1.25).float().mean())
    return {"rmse_m": rmse, "delta1": delta1}


@torch.no_grad()
def evaluate_batch(out: dict, batch: dict) -> dict:
    res = {
        "psnr": psnr(out["gray"], batch["gray"]),
        "ssim": float(ssim(out["gray"], batch["gray"])),
        "ab_l1": float(torch.mean(torch.abs(out["ab"] - batch["ab"]))),
    }
    res.update(depth_metrics(out["inv_depth"], batch["inv_depth"],
                             batch["depth_valid"]))
    return res
