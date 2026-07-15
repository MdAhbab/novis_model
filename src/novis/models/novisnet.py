"""NOVISNet: thermal + echo + sonar tokens -> gray / depth / color+confidence."""

import torch.nn as nn

from .decoder import Decoder
from .fusion import FusionBackbone


class NOVISNet(nn.Module):
    def __init__(self, dim: int = 128, depth: int = 6, heads: int = 4,
                 decoder_chs=(96, 64, 48)):
        super().__init__()
        self.backbone = FusionBackbone(dim=dim, depth=depth, heads=heads)
        self.decoder = Decoder(dim=dim, chs=tuple(decoder_chs))

    def forward(self, thermal, echo, sonar, mask):
        grid = self.backbone(thermal, echo, sonar, mask)
        return self.decoder(grid)

    def param_count(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def build_model(cfg) -> NOVISNet:
    m = cfg.model
    return NOVISNet(dim=m.dim, depth=m.depth, heads=m.heads,
                    decoder_chs=m.decoder_chs)
