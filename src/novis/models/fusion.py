"""Token fusion backbone with learned mask tokens for absent modalities."""

import torch
import torch.nn as nn

from .blocks import SandwichBlock
from .stems import EchoStem, SonarStem, ThermalStem


class FusionBackbone(nn.Module):
    def __init__(self, dim: int = 256, depth: int = 12, heads: int = 8,
                 grid_hw=(12, 16), echo_tokens: int = 24, sonar_tokens: int = 4,
                 ffn_ratio: int = 3, drop_path: float = 0.0):
        super().__init__()
        self.grid_hw = grid_hw
        self.n_grid = grid_hw[0] * grid_hw[1]
        self.thermal_stem = ThermalStem(dim, grid_hw)
        self.echo_stem = EchoStem(dim, echo_tokens)
        self.sonar_stem = SonarStem(dim, sonar_tokens)
        self.skip_ch = self.thermal_stem.skip_ch

        # One learned mask token per modality, broadcast over its slots.
        self.mask_tokens = nn.ParameterDict({
            "thermal": nn.Parameter(torch.zeros(1, 1, dim)),
            "echo": nn.Parameter(torch.zeros(1, 1, dim)),
            "sonar": nn.Parameter(torch.zeros(1, 1, dim)),
        })
        for p in self.mask_tokens.values():
            nn.init.trunc_normal_(p, std=0.02)

        # Linearly increasing stochastic-depth rate over the stack.
        rates = torch.linspace(0.0, drop_path, depth).tolist()
        self.blocks = nn.ModuleList(
            [SandwichBlock(dim, heads, grid_hw, ffn_ratio, rates[i])
             for i in range(depth)])
        self.norm = nn.LayerNorm(dim)

    @staticmethod
    def _apply_mask(tokens, mask_col, mask_token):
        # mask_col: (B,) 1=present, 0=absent
        m = mask_col.view(-1, 1, 1)
        return tokens * m + mask_token * (1.0 - m)

    def forward(self, thermal, echo, sonar, mask):
        t_tokens, t_skip = self.thermal_stem(thermal)
        t = self._apply_mask(t_tokens, mask[:, 0], self.mask_tokens["thermal"])
        # Zero the skip map when thermal is absent so the decoder cannot
        # leak stale spatial detail from a masked modality.
        t_skip = t_skip * mask[:, 0].view(-1, 1, 1, 1)
        e = self._apply_mask(self.echo_stem(echo), mask[:, 1],
                             self.mask_tokens["echo"])
        s = self._apply_mask(self.sonar_stem(sonar), mask[:, 2],
                             self.mask_tokens["sonar"])
        tokens = torch.cat([t, e, s], dim=1)      # (B, 220, D)
        for blk in self.blocks:
            tokens = blk(tokens)
        tokens = self.norm(tokens)
        b, _, d = tokens.shape
        grid = tokens[:, : self.n_grid, :].transpose(1, 2)
        return grid.reshape(b, d, *self.grid_hw), t_skip
