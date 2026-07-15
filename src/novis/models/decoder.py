"""Upsampling decoder (12x16 -> 96x128) and the four output heads."""

import torch
import torch.nn as nn

from .blocks import DWBlock


class Decoder(nn.Module):
    def __init__(self, dim: int = 128, chs=(96, 64, 48)):
        super().__init__()
        stages = []
        cin = dim
        for c in chs:
            stages.append(nn.Sequential(
                nn.Upsample(scale_factor=2, mode="nearest"),
                DWBlock(cin, c),
                DWBlock(c, c),
            ))
            cin = c
        self.stages = nn.Sequential(*stages)
        c = chs[-1]
        def head(cout):
            return nn.Sequential(
                nn.Conv2d(c, c // 2, 3, padding=1),
                nn.GELU(),
                nn.Conv2d(c // 2, cout, 1),
            )
        self.head_gray = head(1)
        self.head_invdepth = head(1)
        self.head_ab = head(2)
        self.head_logvar = head(1)

    def forward(self, x):
        f = self.stages(x)
        return {
            "gray": torch.sigmoid(self.head_gray(f)),
            "inv_depth": torch.sigmoid(self.head_invdepth(f)),
            "ab": torch.tanh(self.head_ab(f)),
            "log_var": torch.clamp(self.head_logvar(f), -6.0, 4.0),
        }
