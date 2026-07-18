"""Building blocks.

Design sources (see refs.bib): sandwich token-mixing layout after
EfficientViT (Liu et al., CVPR 2023); depthwise blocks with squeeze-
excitation after RepViT (Wang et al., CVPR 2024). No plain stacked-conv
backbone anywhere in the model.
"""

import torch
import torch.nn as nn


class DropPath(nn.Module):
    """Stochastic depth: drop the residual branch per sample."""

    def __init__(self, p: float = 0.0):
        super().__init__()
        self.p = p

    def forward(self, x):
        if self.p == 0.0 or not self.training:
            return x
        keep = 1.0 - self.p
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        mask = x.new_empty(shape).bernoulli_(keep)
        return x * mask / keep


class SqueezeExcite(nn.Module):
    def __init__(self, ch: int, r: int = 4):
        super().__init__()
        self.fc = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(ch, ch // r, 1),
            nn.GELU(),
            nn.Conv2d(ch // r, ch, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return x * self.fc(x)


class DWBlock(nn.Module):
    """RepViT-style unit: 3x3 depthwise + SE, then 1x1 expand/project MLP."""

    def __init__(self, cin: int, cout: int, expand: int = 2, se: bool = True):
        super().__init__()
        self.token_mix = nn.Sequential(
            nn.Conv2d(cin, cin, 3, padding=1, groups=cin),
            nn.BatchNorm2d(cin),
            SqueezeExcite(cin) if se else nn.Identity(),
        )
        self.channel_mix = nn.Sequential(
            nn.Conv2d(cin, cin * expand, 1),
            nn.GELU(),
            nn.Conv2d(cin * expand, cout, 1),
            nn.BatchNorm2d(cout),
        )
        self.skip = (nn.Identity() if cin == cout
                     else nn.Conv2d(cin, cout, 1, bias=False))

    def forward(self, x):
        x = x + self.token_mix(x)
        return self.skip(x) + self.channel_mix(x)


class SandwichBlock(nn.Module):
    """EfficientViT-style sandwich over a token sequence.

    Local depthwise mixing on the thermal grid tokens, one multi-head
    self-attention over ALL tokens (cross-modal mixing), then a gated FFN.
    `grid_hw` marks which leading tokens form the spatial grid.
    """

    def __init__(self, dim: int, heads: int, grid_hw: tuple,
                 ffn_ratio: int = 3, drop_path: float = 0.0):
        super().__init__()
        self.grid_h, self.grid_w = grid_hw
        self.n_grid = self.grid_h * self.grid_w
        self.dw = nn.Conv2d(dim, dim, 3, padding=1, groups=dim)
        self.norm1 = nn.LayerNorm(dim)
        self.attn = nn.MultiheadAttention(dim, heads, batch_first=True)
        self.norm2 = nn.LayerNorm(dim)
        hidden = dim * ffn_ratio
        self.ffn_in = nn.Linear(dim, hidden * 2)
        self.ffn_out = nn.Linear(hidden, dim)
        self.act = nn.GELU()
        self.drop_path = DropPath(drop_path)

    def forward(self, tokens):
        # Local mixing on grid tokens only.
        b, n, d = tokens.shape
        grid = tokens[:, : self.n_grid, :]
        rest = tokens[:, self.n_grid:, :]
        g = grid.transpose(1, 2).reshape(b, d, self.grid_h, self.grid_w)
        g = self.dw(g).flatten(2).transpose(1, 2)
        tokens = torch.cat([grid + self.drop_path(g), rest], dim=1)

        # Global cross-modal attention.
        h = self.norm1(tokens)
        a, _ = self.attn(h, h, h, need_weights=False)
        tokens = tokens + self.drop_path(a)

        # Gated FFN.
        h = self.norm2(tokens)
        u, v = self.ffn_in(h).chunk(2, dim=-1)
        tokens = tokens + self.drop_path(self.ffn_out(self.act(u) * v))
        return tokens
