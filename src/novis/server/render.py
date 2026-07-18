"""Array -> PNG rendering for the browser interface.

Colormaps are computed directly (no matplotlib dependency): Turbo via the
published polynomial fit for depth, a blackbody-style ramp for the thermal
input, and an ocean ramp for echo spectrograms.
"""

import base64
import io

import numpy as np
from PIL import Image


def _poly(x, c):
    y = np.zeros_like(x)
    for coef in reversed(c):
        y = y * x + coef
    return y


def turbo(x: np.ndarray) -> np.ndarray:
    """Turbo colormap polynomial approximation; x in [0,1] -> (H,W,3) [0,1]."""
    x = np.clip(x, 0.0, 1.0).astype(np.float32)
    r = _poly(x, [0.13572138, 4.61539260, -42.66032258, 132.13108234,
                  -152.94239396, 59.28637943])
    g = _poly(x, [0.09140261, 2.19418839, 4.84296658, -14.18503333,
                  4.27729857, 2.82956604])
    b = _poly(x, [0.10667330, 12.64194608, -60.58204836, 110.36276771,
                  -89.90310912, 27.34824973])
    return np.clip(np.stack([r, g, b], axis=-1), 0.0, 1.0)


def blackbody(x: np.ndarray) -> np.ndarray:
    """Black -> red -> orange -> yellow -> white ramp for thermal frames."""
    x = np.clip(x, 0.0, 1.0).astype(np.float32)
    r = np.clip(x * 3.0, 0.0, 1.0)
    g = np.clip(x * 3.0 - 1.0, 0.0, 1.0)
    b = np.clip(x * 3.0 - 2.0, 0.0, 1.0)
    return np.stack([r, g, b], axis=-1)


def ocean(x: np.ndarray) -> np.ndarray:
    """Dark blue -> teal -> pale ramp for echo spectrograms."""
    x = np.clip(x, 0.0, 1.0).astype(np.float32)
    r = np.clip(1.6 * x - 0.6, 0.0, 1.0) ** 1.2
    g = np.clip(1.25 * x - 0.05, 0.0, 1.0) ** 1.1
    b = np.clip(0.35 + 0.75 * x, 0.0, 1.0)
    return np.stack([r, g, b], axis=-1)


def to_png_b64(img01: np.ndarray, scale: int = 1) -> str:
    """(H,W) gray or (H,W,3) rgb float [0,1] -> base64 PNG data string."""
    a = np.clip(img01, 0.0, 1.0)
    if a.ndim == 2:
        a = np.repeat(a[..., None], 3, axis=-1)
    u8 = (a * 255.0 + 0.5).astype(np.uint8)
    im = Image.fromarray(u8)
    if scale > 1:
        im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
