"""Convert BatVision-style (echo wav + RGB + depth) triplets into NOVIS shards.

The Audio-Visual BatVision dataset (Brunetto et al., IROS 2023) ships scenes
with binaural echo recordings and aligned RGB-D frames. Release layouts have
changed between versions, so this script takes explicit glob patterns and
pairs files by sorted order of their stem names. ADJUST THE GLOBS to the
release you downloaded before running, and spot-check pairs visually.

Usage example:
  python scripts/prepare_batvision.py ^
      --audio "path/to/scene*/audio/*.wav" ^
      --rgb   "path/to/scene*/rgb/*.png" ^
      --depth "path/to/scene*/depth/*.png" ^
      --depth-scale 0.001 ^
      --out data/processed/batvision
"""

import argparse
import glob
import sys
import wave as wavemod
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from novis.data import degradation as D  # noqa: E402

OUT_H, OUT_W = 96, 128
SHARD = 512


def read_wav(path: str) -> tuple:
    with wavemod.open(path, "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        raw = np.frombuffer(w.readframes(n), dtype=np.int16)
    data = raw.reshape(-1, ch).astype(np.float32) / 32768.0
    return data, sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True, help="glob for echo wav files")
    ap.add_argument("--rgb", required=True, help="glob for RGB frames")
    ap.add_argument("--depth", required=True, help="glob for depth frames")
    ap.add_argument("--depth-scale", type=float, default=0.001,
                    help="multiply raw depth values by this to get meters")
    ap.add_argument("--out", default="data/processed/batvision")
    ap.add_argument("--val-every", type=int, default=10,
                    help="every Nth sample goes to val")
    args = ap.parse_args()

    audio = sorted(glob.glob(args.audio))
    rgb = sorted(glob.glob(args.rgb))
    depth = sorted(glob.glob(args.depth))
    n = min(len(audio), len(rgb), len(depth))
    if n == 0:
        raise SystemExit("no files matched; adjust the glob patterns")
    print(f"pairing {n} triplets (audio {len(audio)}, rgb {len(rgb)}, "
          f"depth {len(depth)})")

    out = Path(args.out)
    bufs = {"train": _newbuf(), "val": _newbuf()}
    counters = {"train": 0, "val": 0}

    for i in range(n):
        wav, sr = read_wav(audio[i])
        # Binaural -> 2 spectrogram channels; mono -> duplicated.
        left = wav[:, 0]
        right = wav[:, 1] if wav.shape[1] > 1 else wav[:, 0]
        echo = np.stack([D.wav_to_spec(left, sr), D.wav_to_spec(right, sr)])

        vis = np.asarray(Image.open(rgb[i]).convert("RGB").resize(
            (OUT_W, OUT_H), Image.BILINEAR))
        gray, ab = D.lab_targets(vis)

        draw = np.asarray(Image.open(depth[i]), dtype=np.float32)
        if draw.ndim == 3:
            draw = draw[..., 0]
        depth_m = np.asarray(Image.fromarray(draw).resize(
            (OUT_W, OUT_H), Image.NEAREST), dtype=np.float32) * args.depth_scale
        valid = (depth_m > 0.05).astype(np.float32)
        depth_m[depth_m <= 0.05] = D.DMAX_M

        rng = np.random.default_rng(i)
        ranges, vflags = D.synth_sonar(depth_m, hfov_deg=55.0, rng=rng)
        sonar = np.zeros(10, np.float32)
        sonar[0:2], sonar[2:4] = ranges, vflags
        sonar[4:8] = ranges.mean()

        split = "val" if i % args.val_every == 0 else "train"
        b = bufs[split]
        b["thermal"].append(np.zeros((1, 24, 32), np.float32))
        b["echo"].append(echo.astype(np.float32))
        b["sonar"].append(sonar)
        b["mask"].append(np.array([0, 1, 1], np.float32))  # echo + sonar
        b["gray"].append(gray[None])
        b["ab"].append(ab.transpose(2, 0, 1))
        b["inv_depth"].append(D.depth_to_inv01(depth_m)[None])
        b["depth_valid"].append(valid[None])
        if len(b["gray"]) >= SHARD:
            counters[split] = _flush(b, out / split, counters[split])

    for split in ("train", "val"):
        counters[split] = _flush(bufs[split], out / split, counters[split])
        print(f"{split}: {counters[split]} shards")


def _newbuf():
    return {k: [] for k in ["thermal", "echo", "sonar", "mask", "gray", "ab",
                            "inv_depth", "depth_valid"]}


def _flush(buf, out_dir: Path, shard_i: int) -> int:
    if not buf["gray"]:
        return shard_i
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / f"shard_{shard_i:04d}.npz",
                        **{k: np.stack(v) for k, v in buf.items()})
    for v in buf.values():
        v.clear()
    return shard_i + 1


if __name__ == "__main__":
    main()
