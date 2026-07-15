"""Modality stems: raw sensor tensors -> token sequences of shared dim."""

import torch
import torch.nn as nn


class ThermalStem(nn.Module):
    """(B,1,24,32) -> (B, 192, D) grid tokens via 2x2 patch embedding."""

    def __init__(self, dim: int, grid_hw=(12, 16)):
        super().__init__()
        self.grid_h, self.grid_w = grid_hw
        self.proj = nn.Conv2d(1, dim, kernel_size=2, stride=2)
        self.pos = nn.Parameter(
            torch.zeros(1, self.grid_h * self.grid_w, dim))
        nn.init.trunc_normal_(self.pos, std=0.02)

    def forward(self, x):
        t = self.proj(x)                          # (B, D, 12, 16)
        t = t.flatten(2).transpose(1, 2)          # (B, 192, D)
        return t + self.pos


class EchoStem(nn.Module):
    """(B,2,64,64) spectrograms -> (B, n_tokens, D)."""

    def __init__(self, dim: int, n_tokens: int = 24):
        super().__init__()
        self.n_tokens = n_tokens
        def dsc(cin, cout, stride):
            return nn.Sequential(
                nn.Conv2d(cin, cin, 3, stride=stride, padding=1, groups=cin),
                nn.Conv2d(cin, cout, 1),
                nn.BatchNorm2d(cout),
                nn.GELU(),
            )
        self.net = nn.Sequential(
            nn.Conv2d(2, 32, 3, stride=2, padding=1),   # 32x32
            nn.GELU(),
            dsc(32, 64, 2),                              # 16x16
            dsc(64, dim, 2),                             # 8x8
        )
        self.pool = nn.AdaptiveAvgPool2d((4, 6))         # 24 tokens
        self.pos = nn.Parameter(torch.zeros(1, n_tokens, dim))
        nn.init.trunc_normal_(self.pos, std=0.02)

    def forward(self, x):
        f = self.pool(self.net(x))                       # (B, D, 4, 6)
        f = f.flatten(2).transpose(1, 2)                 # (B, 24, D)
        return f + self.pos


class SonarStem(nn.Module):
    """(B,10) range vector -> (B, 4, D)."""

    def __init__(self, dim: int, n_tokens: int = 4, in_dim: int = 10):
        super().__init__()
        self.n_tokens = n_tokens
        self.mlp = nn.Sequential(
            nn.Linear(in_dim, dim),
            nn.GELU(),
            nn.Linear(dim, dim * n_tokens),
        )
        self.dim = dim

    def forward(self, x):
        return self.mlp(x).view(x.shape[0], self.n_tokens, self.dim)
