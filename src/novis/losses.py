"""Losses (methodology Section 5.2).

L_total = L_gray + lambda_d * L_depth + lambda_c * L_color
  L_gray : L1 + 0.5 * (1 - SSIM)
  L_depth: masked L1 on inverse depth + edge-aware smoothness
  L_color: heteroscedastic L1  |ab - ab_gt| * exp(-s) + s
"""

import torch
import torch.nn.functional as F


def _gaussian_window(size: int, sigma: float, device, dtype):
    x = torch.arange(size, device=device, dtype=dtype) - size // 2
    g = torch.exp(-(x ** 2) / (2 * sigma ** 2))
    g = (g / g.sum()).unsqueeze(0)
    return (g.t() @ g).unsqueeze(0).unsqueeze(0)


def ssim(a: torch.Tensor, b: torch.Tensor, window: int = 7,
         sigma: float = 1.5) -> torch.Tensor:
    """Mean SSIM over the batch for single-channel images in [0,1]."""
    w = _gaussian_window(window, sigma, a.device, a.dtype)
    pad = window // 2
    mu_a = F.conv2d(a, w, padding=pad)
    mu_b = F.conv2d(b, w, padding=pad)
    var_a = F.conv2d(a * a, w, padding=pad) - mu_a ** 2
    var_b = F.conv2d(b * b, w, padding=pad) - mu_b ** 2
    cov = F.conv2d(a * b, w, padding=pad) - mu_a * mu_b
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    s = ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / (
        (mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2))
    return s.mean()


def gray_loss(pred, target):
    return F.l1_loss(pred, target) + 0.5 * (1.0 - ssim(pred, target))


def depth_loss(pred_inv, target_inv, valid):
    denom = valid.sum().clamp_min(1.0)
    l1 = (torch.abs(pred_inv - target_inv) * valid).sum() / denom
    # Edge-aware smoothness weighted by the *target* gray gradients is
    # applied in the trainer where gray is available; here plain smoothness.
    dx = torch.abs(pred_inv[..., :, 1:] - pred_inv[..., :, :-1]).mean()
    dy = torch.abs(pred_inv[..., 1:, :] - pred_inv[..., :-1, :]).mean()
    return l1 + 0.05 * (dx + dy)


def color_loss(pred_ab, log_var, target_ab):
    err = torch.abs(pred_ab - target_ab).mean(dim=1, keepdim=True)
    return (err * torch.exp(-log_var) + log_var).mean()


def total_loss(out: dict, batch: dict, lambda_d: float = 1.0,
               lambda_c: float = 0.5) -> dict:
    lg = gray_loss(out["gray"], batch["gray"])
    ld = depth_loss(out["inv_depth"], batch["inv_depth"], batch["depth_valid"])
    lc = color_loss(out["ab"], out["log_var"], batch["ab"])
    total = lg + lambda_d * ld + lambda_c * lc
    return {"total": total, "gray": lg.detach(), "depth": ld.detach(),
            "color": lc.detach()}
