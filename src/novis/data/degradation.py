"""Sensor degradation operators.

These turn rich public-dataset frames into signals that statistically match
the NOVIS node's cheap sensors (see NOVIS/docs/methodology.md, Section 4):

  D_t  degrade_thermal : hi-res thermal image  -> 32x24 MLX90640-like frame
  D_s  synth_sonar     : depth map             -> 2 ultrasonic cone returns
  D_e  wav_to_spec     : echo waveform         -> log-magnitude spectrogram

All functions are pure numpy so they run in DataLoader workers without torch.
"""

import numpy as np

# MLX90640 geometry and noise model
THERMAL_H, THERMAL_W = 24, 32
NETD_SIGMA = 0.015          # NETD noise in normalized [0,1] units
DEAD_PIXEL_RATE = 0.02
COLUMN_FPN_SIGMA = 0.006    # fixed-pattern column offset

# HC-SR04 model
SONAR_MAX_M = 4.0
SONAR_CONE_HALF_DEG = 15.0
SONAR_AZIMUTHS_DEG = (-20.0, 20.0)
SONAR_DROPOUT = 0.03

# Depth normalization (inverse-depth in [0,1] between DMIN and DMAX)
DMIN_M, DMAX_M = 0.3, 8.0


def area_downsample(img: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Box-filter downsample by integer-ish factors (crops the remainder)."""
    h, w = img.shape[:2]
    fh, fw = h // out_h, w // out_w
    if fh < 1 or fw < 1:
        raise ValueError(f"source {h}x{w} smaller than target {out_h}x{out_w}")
    img = img[: fh * out_h, : fw * out_w]
    return img.reshape(out_h, fh, out_w, fw).mean(axis=(1, 3))


def degrade_thermal(hi_res: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """D_t: hi-res thermal (H,W) float [0,1] -> (24,32) float [0,1]."""
    t = area_downsample(hi_res.astype(np.float32), THERMAL_H, THERMAL_W)
    gain = 1.0 + rng.normal(0.0, 0.03)
    offset = rng.normal(0.0, 0.02)
    t = t * gain + offset
    t = t + rng.normal(0.0, NETD_SIGMA, t.shape).astype(np.float32)
    t = t + rng.normal(0.0, COLUMN_FPN_SIGMA, (1, THERMAL_W)).astype(np.float32)
    dead = rng.random(t.shape) < DEAD_PIXEL_RATE
    t[dead] = 0.0
    return np.clip(t, 0.0, 1.0)


def depth_to_inv01(depth_m: np.ndarray) -> np.ndarray:
    """Metric depth (meters) -> normalized inverse depth in [0,1]."""
    d = np.clip(depth_m, DMIN_M, DMAX_M)
    inv = 1.0 / d
    lo, hi = 1.0 / DMAX_M, 1.0 / DMIN_M
    return ((inv - lo) / (hi - lo)).astype(np.float32)


def inv01_to_depth(inv01: np.ndarray) -> np.ndarray:
    lo, hi = 1.0 / DMAX_M, 1.0 / DMIN_M
    return 1.0 / (inv01 * (hi - lo) + lo)


def synth_sonar(depth_m: np.ndarray, hfov_deg: float,
                rng: np.random.Generator) -> tuple:
    """D_s: depth map (H,W) meters -> (ranges[2], valid[2]).

    Each HC-SR04 sees a cone; its reading is the minimum depth inside the
    cone footprint, clipped to 4 m, quantized to 1 cm, with random dropout.
    """
    h, w = depth_m.shape
    xs = (np.arange(w) + 0.5) / w - 0.5           # [-0.5, 0.5]
    az = xs * hfov_deg                            # per-column azimuth, degrees
    ranges = np.zeros(2, dtype=np.float32)
    valid = np.zeros(2, dtype=np.float32)
    for i, center in enumerate(SONAR_AZIMUTHS_DEG):
        cols = np.abs(az - center) <= SONAR_CONE_HALF_DEG
        if not cols.any():
            continue
        cone = depth_m[:, cols]
        cone = cone[cone > 0]
        if cone.size == 0:
            continue
        r = float(np.min(cone))
        if r > SONAR_MAX_M or rng.random() < SONAR_DROPOUT:
            continue
        ranges[i] = round(r, 2) / SONAR_MAX_M     # normalized [0,1]
        valid[i] = 1.0
    return ranges, valid


def wav_to_spec(wave: np.ndarray, sr: int = 16000, n_fft: int = 256,
                hop: int = 64, out_h: int = 64, out_w: int = 64) -> np.ndarray:
    """D_e: mono waveform -> (out_h, out_w) log-magnitude spectrogram [0,1]."""
    wave = wave.astype(np.float32)
    n_frames = max(1, 1 + (len(wave) - n_fft) // hop)
    win = np.hanning(n_fft).astype(np.float32)
    frames = np.stack([wave[i * hop: i * hop + n_fft] * win
                       for i in range(n_frames)
                       if i * hop + n_fft <= len(wave)] or
                      [np.zeros(n_fft, dtype=np.float32)])
    mag = np.abs(np.fft.rfft(frames, axis=1))     # (T, n_fft//2+1)
    spec = np.log1p(mag).T                        # (F, T)
    spec = spec / max(spec.max(), 1e-6)
    # Resize to (out_h, out_w) by simple area pooling / edge padding.
    spec = _resize_2d(spec, out_h, out_w)
    return spec.astype(np.float32)


def _resize_2d(a: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Nearest-index resize, dependency-free."""
    h, w = a.shape
    ri = np.clip((np.arange(out_h) * h / out_h).astype(int), 0, h - 1)
    ci = np.clip((np.arange(out_w) * w / out_w).astype(int), 0, w - 1)
    return a[np.ix_(ri, ci)]


# ---------------- Color space (sRGB -> CIELAB), dependency-free ----------------

_M_RGB2XYZ = np.array([[0.4124564, 0.3575761, 0.1804375],
                       [0.2126729, 0.7151522, 0.0721750],
                       [0.0193339, 0.1191920, 0.9503041]], dtype=np.float32)
_WHITE = np.array([0.95047, 1.0, 1.08883], dtype=np.float32)


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB (H,W,3) uint8/float[0,1] -> Lab float32, L in [0,100], ab ~ [-110,110]."""
    x = rgb.astype(np.float32)
    if x.max() > 1.5:
        x = x / 255.0
    lin = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)
    xyz = lin @ _M_RGB2XYZ.T / _WHITE
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16.0 / 116.0)
    L = 116.0 * f[..., 1] - 16.0
    a = 500.0 * (f[..., 0] - f[..., 1])
    b = 200.0 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], axis=-1).astype(np.float32)


def lab_targets(rgb: np.ndarray) -> tuple:
    """RGB frame -> (gray [0,1], ab [-1,1]) training targets."""
    lab = rgb_to_lab(rgb)
    gray = np.clip(lab[..., 0] / 100.0, 0.0, 1.0)
    ab = np.clip(lab[..., 1:] / 110.0, -1.0, 1.0)
    return gray.astype(np.float32), ab.astype(np.float32)
