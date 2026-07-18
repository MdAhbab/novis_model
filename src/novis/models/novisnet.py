"""NOVISNet: thermal + echo + sonar tokens -> gray / depth / optional color."""

import torch.nn as nn

from .decoder import Decoder
from .fusion import FusionBackbone


class NOVISNet(nn.Module):
    def __init__(self, dim: int = 256, depth: int = 12, heads: int = 8,
                 decoder_chs=(256, 192, 128, 96), ffn_ratio: int = 3,
                 drop_path: float = 0.0, color_head: bool = True,
                 grid_hw=(12, 16)):
        super().__init__()
        self.grid_hw = tuple(grid_hw)
        self.out_hw = (self.grid_hw[0] * 2 ** len(decoder_chs),
                       self.grid_hw[1] * 2 ** len(decoder_chs))
        self.color_head = color_head
        self.backbone = FusionBackbone(dim=dim, depth=depth, heads=heads,
                                       grid_hw=self.grid_hw,
                                       ffn_ratio=ffn_ratio,
                                       drop_path=drop_path)
        self.decoder = Decoder(dim=dim, chs=tuple(decoder_chs),
                               skip_ch=self.backbone.skip_ch,
                               color_head=color_head)

    def forward(self, thermal, echo, sonar, mask):
        grid, skip = self.backbone(thermal, echo, sonar, mask)
        return self.decoder(grid, skip)

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def build_model(cfg) -> NOVISNet:
    m = cfg.model
    return NOVISNet(dim=m.dim, depth=m.depth, heads=m.heads,
                    decoder_chs=m.decoder_chs,
                    ffn_ratio=getattr(m, "ffn_ratio", 3),
                    drop_path=getattr(m, "drop_path", 0.0),
                    color_head=getattr(m, "color_head", True))
