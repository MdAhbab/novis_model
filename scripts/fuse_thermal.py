"""Merge the two thermal sensors into one frame - the way one eye works.

BAA sees wide and blurry. BAB sees the middle of that same view about twice
as sharply: it is mounted beside BAA pointing the same way, with roughly half
the field of view spread over the same 32x24 pixels. A human eye does the
same thing - a sharp fovea in the centre, a wide blurry periphery around it.
The merged frame is BAA's whole view with BAB's pixels filling the middle, so
it covers exactly what the ground-truth photo is framed to, with twice the
detail in the centre. A person twice as far away looks about as detailed in
the centre of the merged frame as a person at half that distance does in BAA.

This is NOT stereo. Two eyes get depth from the small difference between
two near-identical views a few cm apart. Here the two views have different
widths and the sensors sit ~1 cm apart, so the disparity at 2 m is a fraction
of a pixel. No depth comes out of this - only detail.

Where BAB's view sits inside BAA's is measured, not assumed: register() finds
the scale and centre that make BAB best match BAA across a run of scenes. On
the first real captures (2026-09-24) BAB covered 0.58 x 0.48 of BAA's frame,
centred at (0.50, 0.48), with a match of r = 0.89. The nominal equal-angle
layout (0.50 x 0.47, centred) scored 0.875 and a pinhole-lens model 0.75.

All inputs are (24, 32) frames already cleaned the usual way - sub-page
offset removed, dead pixels repaired, un-mirrored - in any one unit.
numpy/scipy only.
"""

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates

H, W = 24, 32

# (sx, sy, cx, cy): BAB's view as a fraction of BAA's width and height, and
# its centre in BAA's frame. Equal-angle pixels, co-axial mount.
NOMINAL = (0.50, 0.47, 0.50, 0.50)

_v, _u = (np.mgrid[0:H, 0:W] + 0.5) / np.array([H, W])[:, None, None]


def _sample(img, x, y, order=1):
    """img (24,32) read at normalised coords x, y in [0,1], pixel-centre convention."""
    return map_coordinates(np.asarray(img, float), [y * H - 0.5, x * W - 0.5],
                           order=order, mode="nearest")


def baa_under_bab(A, reg):
    """BAA resampled at the centre of every BAB pixel: what BAA sees there."""
    sx, sy, cx, cy = reg
    return _sample(A, cx + sx * (_u - 0.5), cy + sy * (_v - 0.5))


def register(pairs, min_r=0.6):
    """Find where BAB's view sits in BAA's, from [(A, B), ...] scene pairs.

    Returns (reg, r, fitted). BAB is blurred to BAA's sharpness before
    comparing, so the match rewards alignment rather than BAB's extra detail.
    Scenes are weighted by their contrast - a flat room carries no information
    about alignment. If the best match is weak (r < min_r), the data cannot
    locate the fovea and the nominal layout is returned with fitted=False.
    """
    prepped = []
    for A, B in pairs:
        A = np.asarray(A, float)
        b = gaussian_filter(np.asarray(B, float), 1.0)
        if A.std() < 1e-6 or b.std() < 1e-6:
            continue
        prepped.append((A, (b - b.mean()) / b.std(), A.std() * b.std()))
    if not prepped:
        return NOMINAL, float("nan"), False

    def score(reg):
        tot = wsum = 0.0
        for A, bz, w in prepped:
            a = baa_under_bab(A, reg)
            sd = a.std()
            if sd < 1e-9:
                continue
            tot += w * float(((a - a.mean()) / sd * bz).mean())
            wsum += w
        return tot / wsum if wsum else -1.0

    best = (score(NOMINAL), NOMINAL)
    for sx in np.arange(0.30, 0.671, 0.04):               # coarse
        for sy in np.arange(0.30, 0.671, 0.04):
            for cx in np.arange(0.40, 0.601, 0.04):
                for cy in np.arange(0.40, 0.601, 0.04):
                    s = score((sx, sy, cx, cy))
                    if s > best[0]:
                        best = (s, (sx, sy, cx, cy))
    c = best[1]
    for sx in np.arange(c[0] - 0.04, c[0] + 0.041, 0.01):  # fine, around the coarse best
        for sy in np.arange(c[1] - 0.04, c[1] + 0.041, 0.01):
            for cx in np.arange(c[2] - 0.03, c[2] + 0.031, 0.01):
                for cy in np.arange(c[3] - 0.03, c[3] + 0.031, 0.01):
                    s = score((sx, sy, cx, cy))
                    if s > best[0]:
                        best = (s, (sx, sy, cx, cy))
    r, reg = best
    if r < min_r:
        return NOMINAL, r, False
    return tuple(round(float(x), 3) for x in reg), r, True


def fuse(A, B, reg, out_hw=(96, 128), feather=1.5):
    """One merged frame over BAA's whole field of view.

    Returns (merged, alpha): merged is out_hw in A's units; alpha is where
    BAB's pixels were used (1) versus BAA's (0), for drawing or masking.

    BAB is put on BAA's background level first. The two sensors read the same
    room about 2 C apart on the first captures, and the median gap over the
    overlap is that offset. Only the offset is matched, not the contrast:
    BAB reads a warm body hotter because its smaller pixels mix less
    background into it, which is real detail rather than an error. The edge
    is feathered over `feather` BAB pixels so the fovea has no hard seam.
    """
    sx, sy, cx, cy = reg
    oh, ow = out_hw
    y, x = (np.mgrid[0:oh, 0:ow] + 0.5) / np.array([oh, ow])[:, None, None]
    periph = _sample(A, x, y, order=3)
    u = (x - cx) / sx + 0.5
    v = (y - cy) / sy + 0.5
    fovea = _sample(B, u, v, order=3)
    offset = float(np.median(gaussian_filter(np.asarray(B, float), 1.0)
                             - baa_under_bab(A, reg)))
    fovea = fovea - offset
    edge = np.minimum(np.minimum(u, 1 - u) * W, np.minimum(v, 1 - v) * H)
    alpha = np.clip(edge / feather, 0.0, 1.0)
    return alpha * fovea + (1 - alpha) * periph, alpha
