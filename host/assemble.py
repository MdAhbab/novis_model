"""Turn decoded NOVIS frames into a NOVISNet input batch.

The conversions match the training pipeline so the model sees the same signal
statistics at deployment. Echo spectrograms reuse novis.data.degradation, the
exact operator used to build the training shards.
"""

from __future__ import annotations

from collections import deque

import numpy as np
import torch

from novis.data import degradation as D

from . import protocol as P


def _thermal_to_unit(raw: np.ndarray) -> np.ndarray:
    """int16 centi-Celsius (24x32) -> float [0,1] by per-frame min-max."""
    f = raw.astype(np.float32)
    lo, hi = float(f.min()), float(f.max())
    if hi - lo < 1e-6:
        return np.zeros_like(f)
    return (f - lo) / (hi - lo)


class FrameAssembler:
    """Buffers the latest reading per modality and builds the model input."""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._thermal = None                 # (24,32) float [0,1]
        self._echo = deque(maxlen=2)         # up to 2 (64,64) spectrograms
        self._sonar = None                   # (10,) float
        self.seen = {"thermal": False, "echo": False, "sonar": False}

    def update(self, frame: P.Frame) -> None:
        if frame.type == P.THERMAL:
            raw = np.frombuffer(frame.payload[:P.THERMAL_BYTES],
                                dtype="<i2").reshape(24, 32)
            self._thermal = _thermal_to_unit(raw)
            self.seen["thermal"] = True
        elif frame.type == P.ECHO:
            pcm = np.frombuffer(frame.payload[:P.ECHO_BYTES],
                                dtype="<i2").astype(np.float32) / 32768.0
            self._echo.append(D.wav_to_spec(pcm, sr=16000))
            self.seen["echo"] = True
        elif frame.type == P.SONAR:
            l, r = np.frombuffer(frame.payload[:4], dtype="<u2")
            status = frame.payload[4]
            vec = np.zeros(10, dtype=np.float32)
            rl = min(l / 1000.0, D.SONAR_MAX_M) / D.SONAR_MAX_M
            rr = min(r / 1000.0, D.SONAR_MAX_M) / D.SONAR_MAX_M
            vec[0], vec[1] = rl, rr
            vec[2] = 1.0 if (status & 0x01) else 0.0
            vec[3] = 1.0 if (status & 0x02) else 0.0
            vec[4:8] = (rl + rr) / 2.0
            self._sonar = vec
            self.seen["sonar"] = True

    def reset(self) -> None:
        self.seen = {"thermal": False, "echo": False, "sonar": False}
        self._thermal = None
        self._sonar = None

    def ready(self) -> bool:
        """At least one modality has arrived."""
        return any(self.seen.values())

    def model_input(self) -> dict:
        """Build a batch-of-1 input dict; absent modalities are zeros+mask 0."""
        thermal = np.zeros((1, 24, 32), np.float32)
        echo = np.zeros((2, 64, 64), np.float32)
        sonar = np.zeros(10, np.float32)
        mask = np.zeros(3, np.float32)

        if self._thermal is not None:
            thermal[0] = self._thermal
            mask[0] = 1.0
        if len(self._echo) > 0:
            windows = list(self._echo)
            while len(windows) < 2:
                windows.insert(0, windows[0])
            echo[0], echo[1] = windows[-2], windows[-1]
            mask[1] = 1.0
        if self._sonar is not None:
            sonar = self._sonar
            mask[2] = 1.0

        to = lambda a: torch.from_numpy(a).unsqueeze(0).to(self.device)
        out = {"thermal": to(thermal), "echo": to(echo),
                "sonar": to(sonar), "mask": to(mask)}
        self.reset()
        return out
