"""Datasets.

Sample dict layout (all float32 numpy in the dataset, torch tensors after
collate):

  thermal      (1, 24, 32)   [0,1], zeros if absent
  echo         (2, 64, 64)   [0,1], zeros if absent
  sonar        (10,)         2 ranges + 2 valid flags + 4+2 history slots
  mask         (3,)          [thermal, echo, sonar] presence flags
  gray         (1, 96, 128)  target luminance [0,1]
  ab           (2, 96, 128)  target chrominance [-1,1]
  inv_depth    (1, 96, 128)  target normalized inverse depth [0,1]
  depth_valid  (1, 96, 128)  1 where inv_depth is supervised
"""

from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset

from . import degradation as D

OUT_H, OUT_W = 96, 128
SONAR_DIM = 10
KEYS = ["thermal", "echo", "sonar", "mask", "gray", "ab", "inv_depth", "depth_valid"]


def collate_batch(samples):
    out = {}
    for k in KEYS:
        out[k] = torch.stack([torch.from_numpy(np.ascontiguousarray(s[k]))
                              for s in samples])
    return out


class NOVISShardDataset(Dataset):
    """Reads .npz shards produced by the scripts/prepare_*.py tools.

    Each shard holds arrays named per KEYS with a leading sample axis.
    """

    def __init__(self, shard_dir: str):
        self.files = sorted(Path(shard_dir).glob("*.npz"))
        if not self.files:
            raise FileNotFoundError(f"no .npz shards in {shard_dir}")
        self._index = []           # (file_idx, local_idx)
        self._cache_fi = None
        self._cache = None
        for fi, f in enumerate(self.files):
            with np.load(f) as z:
                n = z["gray"].shape[0]
            self._index.extend((fi, j) for j in range(n))

    def __len__(self):
        return len(self._index)

    def __getitem__(self, i):
        fi, j = self._index[i]
        if self._cache_fi != fi:
            self._cache = {k: v for k, v in np.load(self.files[fi]).items()}
            self._cache_fi = fi
        return {k: self._cache[k][j].astype(np.float32) for k in KEYS}


class SyntheticNOVISDataset(Dataset):
    """Procedural scenes for smoke tests and pipeline debugging.

    Each index deterministically generates a room-like scene: a background
    with a depth gradient plus 1-4 warm rectangular objects. Thermal, echo,
    and sonar observations are derived from the same scene so the fusion
    model has real structure to learn. This is NOT training data for the
    paper; it exists so the code path can be exercised without downloads.
    """

    def __init__(self, n: int = 256, modality_dropout: float = 0.0):
        self.n = n
        self.modality_dropout = modality_dropout

    def __len__(self):
        return self.n

    def __getitem__(self, i):
        rng = np.random.default_rng(1234 + i)
        H, W = OUT_H, OUT_W

        # Background: horizontal luminance ramp, depth ramp back-to-front.
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        gray = 0.25 + 0.3 * (xx / W) + 0.05 * rng.standard_normal((H, W))
        depth_m = 2.0 + 5.0 * (1.0 - yy / H)                # 2..7 m
        ab = np.zeros((H, W, 2), dtype=np.float32)
        temp = np.full((H, W), 0.25, dtype=np.float32)       # cool background

        for _ in range(int(rng.integers(1, 5))):
            w = int(rng.integers(W // 8, W // 3))
            h = int(rng.integers(H // 6, H // 2))
            x0 = int(rng.integers(0, W - w))
            y0 = int(rng.integers(0, H - h))
            d = float(rng.uniform(0.8, 6.0))
            warm = float(rng.uniform(0.6, 1.0))
            lum = float(rng.uniform(0.4, 0.9))
            col = rng.uniform(-0.6, 0.6, size=2).astype(np.float32)
            sl = (slice(y0, y0 + h), slice(x0, x0 + w))
            gray[sl] = lum
            depth_m[sl] = np.minimum(depth_m[sl], d)
            temp[sl] = warm
            ab[sl] = col

        gray = np.clip(gray, 0, 1)
        thermal = D.degrade_thermal(temp, rng)

        # Echo: two channels; ridge row encodes nearest distance, plus noise.
        echo = rng.random((2, 64, 64)).astype(np.float32) * 0.15
        near = float(depth_m.min())
        row = int(np.clip(near / 8.0 * 63, 0, 63))
        echo[:, row: row + 3, :] += 0.7
        echo = np.clip(echo, 0, 1)

        ranges, valid = D.synth_sonar(depth_m, hfov_deg=55.0, rng=rng)
        sonar = np.zeros(SONAR_DIM, dtype=np.float32)
        sonar[0:2] = ranges
        sonar[2:4] = valid
        sonar[4:8] = ranges.mean()                 # flat history placeholder

        mask = np.ones(3, dtype=np.float32)
        if self.modality_dropout > 0:
            for m in range(3):
                if rng.random() < self.modality_dropout:
                    mask[m] = 0.0
            if mask.sum() == 0:                    # never drop everything
                mask[int(rng.integers(0, 3))] = 1.0

        return {
            "thermal": thermal[None].astype(np.float32),
            "echo": echo,
            "sonar": sonar,
            "mask": mask,
            "gray": gray[None].astype(np.float32),
            "ab": ab.transpose(2, 0, 1).astype(np.float32),
            "inv_depth": D.depth_to_inv01(depth_m)[None],
            "depth_valid": np.ones((1, H, W), dtype=np.float32),
        }
