"""PatchGAN discriminator for the optional adversarial term.

Conditional patch discriminator after pix2pix (Isola et al., CVPR 2017):
judges (grayscale reconstruction, upsampled thermal input) pairs so the
critic sees what evidence the generator had. Spectral normalization keeps
the critic Lipschitz-bounded for the hinge objective. Used only when
train.lambda_adv > 0; never exported.
"""

import torch
import torch.nn as nn
from torch.nn.utils import spectral_norm


class PatchDiscriminator(nn.Module):
    def __init__(self, in_ch: int = 2, base: int = 64, n_layers: int = 3):
        super().__init__()
        layers = [
            spectral_norm(nn.Conv2d(in_ch, base, 4, stride=2, padding=1)),
            nn.LeakyReLU(0.2, inplace=True),
        ]
        ch = base
        for i in range(1, n_layers):
            nxt = min(base * 2 ** i, 512)
            layers += [
                spectral_norm(nn.Conv2d(ch, nxt, 4, stride=2, padding=1)),
                nn.LeakyReLU(0.2, inplace=True),
            ]
            ch = nxt
        nxt = min(base * 2 ** n_layers, 512)
        layers += [
            spectral_norm(nn.Conv2d(ch, nxt, 4, stride=1, padding=1)),
            nn.LeakyReLU(0.2, inplace=True),
            spectral_norm(nn.Conv2d(nxt, 1, 4, stride=1, padding=1)),
        ]
        self.net = nn.Sequential(*layers)

    def forward(self, gray, thermal_up):
        return self.net(torch.cat([gray, thermal_up], dim=1))


def d_hinge_loss(real_logits, fake_logits):
    return (torch.relu(1.0 - real_logits).mean()
            + torch.relu(1.0 + fake_logits).mean())


def g_hinge_loss(fake_logits):
    return -fake_logits.mean()
