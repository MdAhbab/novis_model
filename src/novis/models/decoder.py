"""Upsampling decoder and the output heads.

Each stage upsamples 2x with a 1x1 conv + PixelShuffle, then refines with two
depthwise blocks. With a 12x16 token grid and four stages the output is
192x256. The thermal stem's 24x32 feature map is injected after the first
stage as a skip connection, restoring spatial detail lost in tokenization.
"""

import torch
import torch.nn as nn

from .blocks import DWBlock


class UpStage(nn.Module):
    def __init__(self, cin: int, cout: int):
        super().__init__()
        self.up = nn.Sequential(
            nn.Conv2d(cin, cout * 4, 1),
            nn.PixelShuffle(2),
        )
        self.refine = nn.Sequential(DWBlock(cout, cout), DWBlock(cout, cout))

    def forward(self, x):
        return self.refine(self.up(x))


class Decoder(nn.Module):
    def __init__(self, dim: int = 256, chs=(256, 192, 128, 96),
                 skip_ch: int = 128, color_head: bool = True):
        super().__init__()
        self.color_head = color_head
        self.stages = nn.ModuleList()
        cin = dim
        for c in chs:
            self.stages.append(UpStage(cin, c))
            cin = c
        # Skip fusion at the 24x32 stage (after the first upsample).
        self.skip_proj = nn.Conv2d(skip_ch, chs[0], 1)

        c = chs[-1]
        def head(cout):
            return nn.Sequential(
                nn.Conv2d(c, c // 2, 3, padding=1),
                nn.GELU(),
                nn.Conv2d(c // 2, cout, 1),
            )
        self.head_gray = head(1)
        self.head_invdepth = head(1)
        if color_head:
            self.head_ab = head(2)
            self.head_logvar = head(1)

    def forward(self, x, skip=None):
        for i, stage in enumerate(self.stages):
            x = stage(x)
            if i == 0 and skip is not None:
                x = x + self.skip_proj(skip)
        out = {
            "gray": torch.sigmoid(self.head_gray(x)),
            "inv_depth": torch.sigmoid(self.head_invdepth(x)),
        }
        if self.color_head:
            out["ab"] = torch.tanh(self.head_ab(x))
            out["log_var"] = torch.clamp(self.head_logvar(x), -6.0, 4.0)
        return out
