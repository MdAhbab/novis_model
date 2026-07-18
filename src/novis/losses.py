"""Losses (methodology Section 5.2).

L_total = L_gray + lambda_p * L_perc + lambda_d * L_depth
          + lambda_c * L_color + lambda_a * L_adv
  L_gray : L1 + 0.5 * (1 - SSIM)
  L_perc : VGG16 feature L1 (Johnson et al., 2016) on the grayscale output
  L_depth: masked L1 on inverse depth + edge-aware smoothness
  L_color: heteroscedastic L1  |ab - ab_gt| * exp(-s) + s   (color head only)
  L_adv  : hinge generator loss from the PatchGAN critic (optional)
"""

import torch
import torch.nn as nn
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


class PerceptualLoss(nn.Module):
    """L1 distance between VGG16 features of prediction and target.

    Grayscale inputs are replicated to three channels and normalized with
    ImageNet statistics. Uses relu1_2, relu2_2, and relu3_3 activations.
    Weights are frozen; the module adds no trainable parameters.
    """

    def __init__(self):
        super().__init__()
        from torchvision.models import VGG16_Weights, vgg16
        feats = vgg16(weights=VGG16_Weights.IMAGENET1K_V1).features.eval()
        self.slice1 = nn.Sequential(*feats[:4])    # relu1_2
        self.slice2 = nn.Sequential(*feats[4:9])   # relu2_2
        self.slice3 = nn.Sequential(*feats[9:16])  # relu3_3
        for p in self.parameters():
            p.requires_grad_(False)
        self.register_buffer(
            "mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer(
            "std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def _norm(self, x):
        return (x.repeat(1, 3, 1, 1) - self.mean) / self.std

    def forward(self, pred, target):
        a, b = self._norm(pred), self._norm(target)
        loss = pred.new_zeros(())
        for sl in (self.slice1, self.slice2, self.slice3):
            a, b = sl(a), sl(b)
            loss = loss + F.l1_loss(a, b)
        return loss


def gray_loss(pred, target):
    return F.l1_loss(pred, target) + 0.5 * (1.0 - ssim(pred, target))


def depth_loss(pred_inv, target_inv, valid):
    denom = valid.sum().clamp_min(1.0)
    l1 = (torch.abs(pred_inv - target_inv) * valid).sum() / denom
    dx = torch.abs(pred_inv[..., :, 1:] - pred_inv[..., :, :-1]).mean()
    dy = torch.abs(pred_inv[..., 1:, :] - pred_inv[..., :-1, :]).mean()
    return l1 + 0.05 * (dx + dy)


def color_loss(pred_ab, log_var, target_ab):
    err = torch.abs(pred_ab - target_ab).mean(dim=1, keepdim=True)
    return (err * torch.exp(-log_var) + log_var).mean()


def total_loss(out: dict, batch: dict, lambda_d: float = 1.0,
               lambda_c: float = 0.5, lambda_p: float = 0.0,
               perceptual: PerceptualLoss | None = None) -> dict:
    lg = gray_loss(out["gray"], batch["gray"])
    ld = depth_loss(out["inv_depth"], batch["inv_depth"], batch["depth_valid"])
    total = lg + lambda_d * ld
    parts = {"gray": lg.detach(), "depth": ld.detach()}
    if "ab" in out:
        lc = color_loss(out["ab"], out["log_var"], batch["ab"])
        total = total + lambda_c * lc
        parts["color"] = lc.detach()
    if perceptual is not None and lambda_p > 0.0:
        lp = perceptual(out["gray"], batch["gray"])
        total = total + lambda_p * lp
        parts["perc"] = lp.detach()
    parts["total"] = total
    return parts
