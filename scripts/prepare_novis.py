"""Convert dashboard captures from the real NOVIS node into training shards.

Input is one or more .json files exported by firmware/dashboard/dashboard.ino
("Download dataset .json"). Each file holds a metadata header, a scene table
(scene id -> ground-truth photo), and a flat list of samples that each point
at one scene.

Unlike prepare_llvip.py (thermal only) and prepare_batvision.py (echo +
sonar), this is the only corpus where all three modalities are real hardware
readings, so mask is [1,1,1].

Depth: the node has no depth sensor, so inv_depth is written as zeros with
depth_valid all-zero - the training loss masks it out. Sonar still carries
the two real ranges, which is the only metric distance the node measures.

The train/val split is BY SCENE, never by sample. Samples from one scene are
near-duplicates of each other; splitting them randomly would put copies of
the same scene on both sides and report a validation score that means
nothing.

Usage:
  python scripts/prepare_novis.py --captures "data/real_capture/*.json" ^
      --out data/processed/novis
  python scripts/prepare_novis.py --captures "data/real_capture/*.json" ^
      --out data/processed/novis --held-out-scenes bedroom-03,kitchen-01

Two thermal sensors (--baa-max-range):
  A wide-FOV, shorter-range MLX90640 ("BAA") and a narrower-FOV, longer-range
  one ("BAB") are complementary, not redundant - see
  docs/data_collection_protocol.md section 4.2c. The dashboard stores BOTH
  arrays on every sample (thermal = BAA, thermalFar = BAB) and defers the
  choice of which one is the model's actual `thermal` input to here, per
  scene, by distance - the model's input shape never changes:

    python scripts/prepare_novis.py --captures "data/real_capture/*.json" ^
        --out data/processed/novis --baa-max-range 2.5 --r-use 7.5

  Scenes at or under --baa-max-range use BAA's frame (matches the FOV/range
  it was calibrated for); scenes beyond it use BAB's, if BAB's sensor was
  actually working for that sample (falls back to BAA with a warning if not -
  never silently drops the sample). --r-use is then BAB's measured usable
  range (its own 4.2b calibration), not BAA's - it is the point beyond which
  *neither* sensor carries anything useful, so that is where the stress-set
  cutoff belongs now. Omit --baa-max-range to always use BAA, matching every
  session recorded before BAB was added - the two flags are independent and
  each defaults off.

Dead pixels (--dead-pixel-thresh):
  MLX90640 parts are sold with a small number of dead or deviating pixels as
  a documented tolerance, and the Adafruit driver does not repair them, so
  they show up as a fixed-position dot in every frame that sensor ever takes.
  On by default: any pixel sitting more than --dead-pixel-thresh degrees off
  its own neighbours in more than --dead-pixel-frac of all frames is filled
  from those neighbours, per sensor, and reported. Pass --dead-pixel-thresh 0
  to keep the raw readings. Nothing is changed in the capture .json - the raw
  export stays the record of what the hardware actually returned.

Operating-range bucketing (--r-use):
  The sensors have a real, finite usable distance - HC-SR04 caps hard at 4 m,
  and MLX90640's thermal contrast against a room fades out well before that.
  A photo can show a doorway 6 m away in perfect detail while the sensors
  carry almost nothing about it at that range; training on that pair teaches
  the model to hallucinate structure its input never supported. Measure your
  module's actual usable depth once (docs/data_collection_protocol.md
  section 4.2b) and pass it here:

    python scripts/prepare_novis.py --captures "data/real_capture/*.json" ^
        --out data/processed/novis --r-use 2.5

  Every scene needs its "main surface distance (m)" filled in (the dashboard
  already asks for this). Scenes at or under --r-use go into train/val as
  usual, tagged near/mid/far-valid for the paper's table. Scenes beyond it go
  into a separate out/stress/ split instead of train or val - not thrown
  away, but not allowed to teach the model to invent detail it cannot sense.
  Report both: reconstruction quality within range, and graceful degradation
  beyond it. That is a stronger result than silently averaging the two.
"""

import argparse
import base64
import glob
import io
import json
import sys
import warnings
from pathlib import Path

import numpy as np
from PIL import Image

# degradation.py is pure numpy by design, but importing it as novis.data.*
# pulls in the package __init__ and therefore torch. Preparing a dataset
# should not need a working CUDA/torch install, so import the module directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "novis"
                       / "data"))

import degradation as D  # noqa: E402

OUT_H, OUT_W = 192, 256      # must match data.out_hw in the training config
SHARD = 512
THERMAL_H, THERMAL_W = 24, 32
ECHO_N, SR = 960, 16000
KEYS = ["thermal", "echo", "sonar", "mask", "gray", "ab", "inv_depth",
        "depth_valid"]


def decode_photo(data_uri: str) -> np.ndarray:
    """Scene photo (JPEG data URI from the dashboard) -> RGB at OUT_H x OUT_W."""
    b64 = data_uri.split(",", 1)[1]
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    return np.asarray(img.resize((OUT_W, OUT_H), Image.BILINEAR))


def thermal_to_01(centi_c: np.ndarray, mode: str, lo_c: float,
                  hi_c: float) -> np.ndarray:
    """MLX90640 centi-Celsius -> (24, 32) float [0,1].

    'fixed' maps an absolute temperature window, so a person is the same
    brightness in every scene and the numbers stay physically meaningful.
    'perframe' rescales each frame to its own min/max, which is what the
    8-bit thermal cameras behind LLVIP effectively do - closer to the
    pretraining distribution, but it amplifies sensor noise in a room with
    no warm object in view. Fixed is the default; the flag is there so the
    choice can be ablated rather than assumed.
    """
    t = centi_c.reshape(THERMAL_H, THERMAL_W).astype(np.float32) / 100.0
    if mode == "perframe":
        lo, hi = float(t.min()), float(t.max())
        if hi - lo < 0.5:            # near-uniform frame: do not amplify noise
            lo, hi = lo_c, hi_c
    else:
        lo, hi = lo_c, hi_c
    return np.clip((t - lo) / max(hi - lo, 1e-6), 0.0, 1.0).astype(np.float32)


def _neighbour_median(t: np.ndarray) -> np.ndarray:
    """Median of each pixel's 8 neighbours, over a stack of (N, H, W) frames.

    Edge pixels just have fewer neighbours (nanmedian over the ones that
    exist) rather than being skipped, so a dead pixel sitting on the border is
    still detectable and still repairable. NaNs already in the input are
    excluded too, which is what lets repair_dead() avoid filling one dead
    pixel from another.
    """
    n, h, w = t.shape
    pad = np.full((n, h + 2, w + 2), np.nan, np.float32)
    pad[:, 1:-1, 1:-1] = t
    stack = np.stack([pad[:, dy:dy + h, dx:dx + w]
                      for dy in (0, 1, 2) for dx in (0, 1, 2)
                      if not (dy == 1 and dx == 1)])
    # An all-NaN slice is a real, handled case (a dead pixel whose neighbours
    # are all dead too); repair_dead falls back to the frame median there, so
    # the warning would only be noise.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(stack, axis=0)


def dead_pixel_mask(frames, thresh_c: float, min_frac: float,
                    max_frames: int = 500) -> np.ndarray:
    """Positions that sit far off their own neighbours in nearly every frame.

    MLX90640 parts ship with a handful of dead/deviating pixels as a
    documented tolerance, and the Adafruit driver's getFrame() does not repair
    them (it never calls MLX90640_BadPixelsCorrection), so they arrive here as
    a fixed-position spike or hole in every single frame. Left alone they are
    a constant artefact in the model's input, and with --thermal-norm perframe
    one of them sets the normalisation for the whole frame.

    The "in nearly every frame" test is what makes this safe: a real warm
    object moves between scenes and is never present in all of them, so a
    small person-at-distance blob cannot be mistaken for a defect and erased.
    Frames are subsampled because a few hundred already settle the question.
    """
    if not frames:
        return np.zeros((THERMAL_H, THERMAL_W), bool)
    step = max(1, len(frames) // max_frames)
    t = np.stack(frames[::step]).astype(np.float32) / 100.0
    dev = np.abs(t - _neighbour_median(t))
    hits = np.nansum(dev > thresh_c, axis=0)
    return (hits / t.shape[0]) >= min_frac


# MLX90640 in chess mode reads its pixels as two interleaved sub-pages, the
# black and white squares of a chessboard, at different moments. Whatever
# shifts between the two reads - the sensor's own temperature estimate, a
# moving person, a read stretched by WiFi - lands on one colour of square only.
CHESS = (np.add.outer(np.arange(THERMAL_H), np.arange(THERMAL_W)) % 2).astype(bool)


def remove_subpage_offset(frame: np.ndarray) -> np.ndarray:
    """Cancel the offset between the two chess sub-pages of one frame.

    Measured on the first real captures (24 Sept 2026): BAA's sub-pages sat
    +2.5 to -5.3 C apart, varying scene to scene and frame to frame - as large
    as a person's whole contrast against a room, drawn as a chessboard over
    every frame. Each sub-page samples the same scene at every other pixel, so
    for any real scene their medians agree; the gap between them is the
    artefact, not the room. Splitting it evenly between the two leaves real
    edges alone, which a blur would not.
    """
    f = frame.astype(np.float32)
    d = float(np.median(f[CHESS]) - np.median(f[~CHESS]))
    out = f.copy()
    out[CHESS] -= d / 2
    out[~CHESS] += d / 2
    return out


def repair_dead(centi_c: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Replace masked pixels with the median of their live neighbours."""
    if not mask.any():
        return centi_c
    holed = centi_c.astype(np.float32).copy()
    holed[mask] = np.nan
    fill = _neighbour_median(holed[None])[0]
    out = centi_c.astype(np.float32).copy()
    out[mask] = fill[mask]
    # A dead pixel ringed entirely by dead pixels has no live neighbour to
    # borrow from; fall back to the frame's own median rather than emitting a
    # NaN that would poison the shard silently.
    still_nan = np.isnan(out)
    if still_nan.any():
        out[still_nan] = float(np.nanmedian(holed))
    return out


def echo_to_spec(echo_int16) -> np.ndarray:
    """960 int16 samples -> (2, 64, 64) log-magnitude spectrogram.

    The node has one microphone; both channels carry it, matching how
    prepare_batvision.py duplicates a mono recording.
    """
    wave = np.asarray(echo_int16, dtype=np.float32) / 32768.0
    spec = D.wav_to_spec(wave, sr=SR)
    return np.stack([spec, spec]).astype(np.float32)


def sonar_vector(left_mm: int, right_mm: int) -> np.ndarray:
    """Two HC-SR04 readings -> the model's 10-wide sonar vector.

    0 mm from the firmware means no echo came back inside the 30 ms timeout,
    which is a missing reading, not a zero distance - it sets the valid flag
    to 0 the same way degradation.synth_sonar drops a cone.
    """
    v = np.zeros(10, dtype=np.float32)
    for i, mm in enumerate((left_mm, right_mm)):
        if mm and 0 < mm / 1000.0 <= D.SONAR_MAX_M:
            v[i] = (mm / 1000.0) / D.SONAR_MAX_M
            v[i + 2] = 1.0
    known = [v[i] for i in (0, 1) if v[i + 2] > 0]
    v[4:8] = float(np.mean(known)) if known else 0.0   # history placeholder
    return v


def select_thermal(sample: dict, distance_m, baa_max_range: float, sid: str,
                   fallback_count: dict) -> list:
    """Pick BAA's or BAB's frame for one sample, per docs/data_collection_protocol.md
    section 4.2c. Always returns a usable array - a missing/failed BAB frame
    falls back to BAA rather than dropping the sample, but that fallback is
    counted so it shows up in the summary instead of silently degrading the
    far end of the dataset.
    """
    wants_far = (distance_m is not None and distance_m > baa_max_range)
    if not wants_far:
        return sample["thermal"]
    far = sample.get("thermalFar")
    if far is not None and sample.get("thermalFarOk", True):
        return far
    fallback_count[sid] = fallback_count.get(sid, 0) + 1
    return sample["thermal"]


def load_captures(patterns) -> tuple:
    """Read every export, returning (scene id -> full scene dict, samples).

    The scene dict keeps every field the dashboard stored (photo, room,
    distanceM, people, lighting, note) - not just the photo - so downstream
    steps like range bucketing have something to bucket on.

    Samples are DE-DUPLICATED across files. Every download the dashboard makes
    contains the whole tab, not just what is new since the last one, so a
    session downloaded after scene 7 and again at the end produces two files
    where the second wholly contains the first. Ingesting both without this
    would train on scenes 1-7 twice over - silently, and invisibly in every
    summary. A sample is identified by (sceneId, seq, deviceMs): seq is the
    node's own frame counter, which the dashboard already refuses to store
    twice, and deviceMs separates two boots that both counted from zero.
    """
    scenes, samples = {}, []
    seen = set()
    dupes = 0
    files = []
    for p in patterns:
        files.extend(sorted(glob.glob(p)))
    if not files:
        raise SystemExit(f"no capture files matched {patterns}")

    for f in files:
        with open(f, encoding="utf-8") as fh:
            doc = json.load(fh)
        file_scenes = doc.get("scenes") or {}
        if not file_scenes:
            raise SystemExit(
                f"{f} has no scenes block - it was exported by a dashboard "
                f"build older than the ground-truth photo support, and has "
                f"no images to train against")
        for sid, sc in file_scenes.items():
            if sid in scenes:
                continue
            scenes[sid] = sc
        # Echo recorded before the capture fix (dashboard meta without
        # echo.capture == "aligned-v2") began every window with 384-742 zero
        # samples and never contained the chirp - it is not an echo at all.
        aligned = ((doc.get("meta") or {}).get("echo") or {}).get("capture") == "aligned-v2"
        kept, dropped, dup_here = [], 0, 0
        for s in doc["samples"]:
            if not s.get("thermalOk", True):
                dropped += 1
                continue
            key = (s.get("sceneId"), s.get("seq"), s.get("deviceMs"))
            if key in seen:
                dup_here += 1
                continue
            seen.add(key)
            s["_echoAligned"] = aligned
            kept.append(s)
        dupes += dup_here
        samples.extend(kept)
        print(f"{f}: {len(kept)} samples, {len(file_scenes)} scenes"
              + (f" ({dropped} dropped: thermal read failed)" if dropped else "")
              + (f" ({dup_here} already seen in an earlier file)"
                 if dup_here else ""))
    if dupes:
        print(f"  -> {dupes} duplicate sample(s) ignored. This is normal and "
              f"expected when a session was downloaded more than once; every "
              f"download holds the whole session, so the files overlap.")
    return scenes, samples


def range_bucket(distance_m, r_use: float) -> str:
    """near / mid / far-valid / beyond, per docs/data_collection_protocol.md
    section 4.2b. Mid/far-valid split at 0.7 x r_use, matching the buckets
    used for the paper's operating-range table."""
    if distance_m is None:
        return "unknown"
    if distance_m > r_use:
        return "beyond"
    if distance_m <= r_use * 0.35:
        return "near"
    if distance_m <= r_use * 0.7:
        return "mid"
    return "far-valid"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", nargs="+", required=True,
                    help="glob(s) for dashboard .json exports")
    ap.add_argument("--out", default="data/processed/novis")
    ap.add_argument("--held-out-scenes", default="",
                    help="comma-separated scene ids forced into val; without "
                         "this, every Nth scene goes to val")
    ap.add_argument("--val-every", type=int, default=5,
                    help="every Nth scene (by sorted id) goes to val")
    ap.add_argument("--thermal-norm", choices=["fixed", "perframe"],
                    default="fixed")
    ap.add_argument("--temp-min", type=float, default=15.0,
                    help="degrees C mapped to 0.0 when --thermal-norm fixed")
    ap.add_argument("--temp-max", type=float, default=40.0,
                    help="degrees C mapped to 1.0 when --thermal-norm fixed")
    ap.add_argument("--r-use", type=float, default=None,
                    help="measured usable sensing range in metres - BAB's, if "
                         "--baa-max-range is also given, since BAB then covers "
                         "the far end (see docs/data_collection_protocol.md "
                         "section 4.2b/4.2c). Scenes whose distanceM exceeds "
                         "this go to out/stress/ instead of train/val. Omit to "
                         "disable bucketing and keep the old behaviour.")
    ap.add_argument("--baa-max-range", type=float, default=None,
                    help="distance in metres beyond which BAB's frame is used "
                         "instead of BAA's for the model's `thermal` input "
                         "(section 4.2c). Omit to always use BAA, matching "
                         "sessions recorded before BAB was added.")
    ap.add_argument("--dead-pixel-thresh", type=float, default=5.0,
                    help="degrees C a pixel must sit off its neighbours by to "
                         "count as deviating in one frame (section 4.2d). "
                         "0 disables dead-pixel repair entirely.")
    ap.add_argument("--dead-pixel-frac", type=float, default=0.9,
                    help="fraction of frames a pixel must deviate in before "
                         "it is treated as dead rather than as a real object")
    ap.add_argument("--raw-orientation", action="store_true",
                    help="keep thermal in the sensor's raw order, which is "
                         "mirrored left-right against the scene (confirmed "
                         "by hand 2026-09-26); default flips it to match the photo")
    ap.add_argument("--no-subpage-fix", action="store_true",
                    help="keep the raw chess-pattern offset between the two "
                         "MLX90640 sub-pages instead of cancelling it")
    args = ap.parse_args()

    scenes, samples = load_captures(args.captures)
    subfix = (lambda f: f) if args.no_subpage_fix else remove_subpage_offset

    # Report the sub-page offset every run - it is a property of the capture,
    # worth seeing even when it is being corrected.
    for name, key, okkey in (("BAA", "thermal", "thermalOk"),
                             ("BAB", "thermalFar", "thermalFarOk")):
        offs = [float(np.median(f[CHESS]) - np.median(f[~CHESS])) / 100
                for f in (np.asarray(s[key], np.float32).reshape(THERMAL_H, THERMAL_W)
                          for s in samples
                          if s.get(key) is not None and s.get(okkey, True))]
        if offs:
            a = np.abs(offs)
            print(f"{name}: chess sub-page offset median {np.median(a):.2f} C, "
                  f"worst {a.max():.2f} C"
                  + ("  (left in: --no-subpage-fix)" if args.no_subpage_fix
                     else "  - cancelled per frame"))

    # One mask per sensor for the whole run: a dead pixel is a property of the
    # silicon, not of a scene, so pooling every frame is exactly what makes
    # "off in essentially every frame" a meaningful test.
    if args.dead_pixel_thresh > 0:
        dead = {}
        for name, key, okkey in (("BAA", "thermal", "thermalOk"),
                                 ("BAB", "thermalFar", "thermalFarOk")):
            frames = [subfix(np.asarray(s[key]).reshape(THERMAL_H, THERMAL_W))
                      for s in samples
                      if s.get(key) is not None and s.get(okkey, True)]
            dead[key] = dead_pixel_mask(frames, args.dead_pixel_thresh,
                                        args.dead_pixel_frac)
            n_dead = int(dead[key].sum())
            if not frames:
                continue
            if n_dead == 0:
                print(f"{name}: no dead pixels detected in {len(frames)} frames")
            else:
                at = ", ".join(f"({x},{y})" for y, x in zip(*np.where(dead[key])))
                print(f"{name}: {n_dead} dead pixel(s) at {at} - repaired from "
                      f"neighbours in every frame")
            # A handful is the documented part tolerance; a large patch is a
            # different failure (cracked lens, bad bus) and should not be
            # quietly smoothed over into plausible-looking data.
            if n_dead > 10:
                print(f"WARNING: {n_dead} dead pixels on {name} is well past "
                      f"normal part tolerance - inspect the sensor before "
                      f"trusting this data, or raise --dead-pixel-thresh if "
                      f"the scenes really were this high-contrast.")
    else:
        dead = {"thermal": np.zeros((THERMAL_H, THERMAL_W), bool),
                "thermalFar": np.zeros((THERMAL_H, THERMAL_W), bool)}

    scene_bucket = {}
    if args.r_use is not None:
        missing = [sid for sid, sc in scenes.items()
                   if sc.get("distanceM") is None]
        if missing:
            print(f"\nWARNING: {len(missing)} scene(s) have no distanceM, so "
                  f"--r-use cannot bucket them - they will still go to "
                  f"train/val as 'unknown' range: {sorted(missing)[:10]}"
                  + (" ..." if len(missing) > 10 else ""))
        scene_bucket = {sid: range_bucket(sc.get("distanceM"), args.r_use)
                        for sid, sc in scenes.items()}

    # Scenes beyond r_use never enter train/val, so the val fraction should
    # be computed over the scenes that actually can - otherwise --val-every
    # silently drifts as the stress fraction of the dataset changes.
    ids = sorted(scenes)
    in_range_ids = [sid for sid in ids if scene_bucket.get(sid) != "beyond"]
    if args.held_out_scenes.strip():
        val_ids = {s.strip() for s in args.held_out_scenes.split(",")
                   if s.strip()}
        unknown = val_ids - set(ids)
        if unknown:
            raise SystemExit(f"--held-out-scenes names unknown scenes: "
                             f"{sorted(unknown)}")
    else:
        val_ids = {sid for i, sid in enumerate(in_range_ids)
                   if i % args.val_every == 0}
    print(f"\n{len(ids)} scenes, {len(samples)} samples\n"
          f"val scenes ({len(val_ids)} of {len(in_range_ids)} in-range): "
          f"{sorted(val_ids)}")

    # BAB coverage, reported even though BAA-centred runs never read it. The
    # capture .json is the only archive of BAB, and the whole point of storing
    # it (decision D6) is the two-channel ablation later - which is worthless
    # if BAB quietly died halfway through a session and nobody noticed until
    # months afterwards. Checked here because this is the one command that is
    # certain to be run after every session.
    n_far = sum(1 for s in samples
                if s.get("thermalFar") is not None
                and s.get("thermalFarOk", True))
    if n_far == 0:
        print("\nBAB: not recorded in this capture (older dashboard build, or "
              "the sensor was down all session). BAA-only runs are unaffected; "
              "the two-channel comparison will not be possible on this data.")
    elif n_far < len(samples):
        bad = {}
        for s in samples:
            if s.get("thermalFar") is None or not s.get("thermalFarOk", True):
                bad[s["sceneId"]] = bad.get(s["sceneId"], 0) + 1
        print(f"\nBAB: recorded on {n_far}/{len(samples)} samples "
              f"({100 * n_far / len(samples):.0f}%). NOT used as model input "
              f"here, archived for later.")
        print(f"WARNING: BAB was missing or NOT FOUND on "
              f"{len(samples) - n_far} sample(s) across {len(bad)} scene(s): "
              f"{sorted(bad)[:8]}" + (" ..." if len(bad) > 8 else ""))
        print("  Those scenes cannot take part in a two-channel comparison. "
              "If BAB is still down, fix it before the next session.")
    else:
        print(f"\nBAB: recorded on all {n_far} samples. Not used as model "
              f"input here (BAA-centred), archived in the .json for the "
              f"two-channel ablation later.")

    # Decode each scene photo once; every sample in the scene reuses it.
    targets = {}
    for sid, sc in scenes.items():
        gray, ab = D.lab_targets(decode_photo(sc["photo"]))
        targets[sid] = (gray[None], ab.transpose(2, 0, 1))

    out = Path(args.out)
    splits = ("train", "val", "stress") if args.r_use is not None else ("train", "val")
    bufs = {sp: {k: [] for k in KEYS} for sp in splits}
    counters = {sp: 0 for sp in splits}
    n_used = {sp: 0 for sp in splits}
    bucket_counts = {}
    far_fallbacks = {}
    used_far = 0
    echo_state = {"ok": 0, "old": 0, "unheard": 0}
    zeros_depth = np.zeros((1, OUT_H, OUT_W), np.float32)

    for s in samples:
        sid = s["sceneId"]
        if sid not in targets:
            continue                       # sample whose scene never exported

        if args.r_use is not None:
            bucket = scene_bucket[sid]
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
            split = "stress" if bucket == "beyond" else (
                "val" if sid in val_ids else "train")
        else:
            split = "val" if sid in val_ids else "train"

        b = bufs[split]
        gray, ab = targets[sid]

        if args.baa_max_range is not None:
            distance_m = scenes[sid].get("distanceM")
            thermal_src = select_thermal(s, distance_m, args.baa_max_range,
                                         sid, far_fallbacks)
            is_far = thermal_src is s.get("thermalFar")
            used_far += is_far
        else:
            thermal_src = s["thermal"]
            is_far = False

        # Repair before normalising - a dead pixel reading 0 C would otherwise
        # set the low end of the whole frame under --thermal-norm perframe.
        raw = np.asarray(thermal_src).reshape(THERMAL_H, THERMAL_W)
        raw = subfix(raw)
        raw = repair_dead(raw, dead["thermalFar" if is_far else "thermal"])
        if not args.raw_orientation:
            raw = raw[:, ::-1]      # un-mirror: left in the frame = left in the photo
        b["thermal"].append(thermal_to_01(raw, args.thermal_norm,
                                          args.temp_min, args.temp_max)[None])
        b["echo"].append(echo_to_spec(s["echo"]))
        b["sonar"].append(sonar_vector(s["sonarLeftMm"], s["sonarRightMm"]))
        # mask order is [thermal, echo, sonar]. Echo counts as present only if
        # the window was aligned to the chirp and the chirp was actually heard;
        # otherwise the model is told it is missing rather than fed noise
        # labelled as signal.
        onset = s.get("echoOnset")
        echo_ok = bool(s.get("_echoAligned")) and onset is not None and onset >= 0
        echo_state[("ok" if echo_ok else
                    "old" if not s.get("_echoAligned") else "unheard")] += 1
        b["mask"].append(np.array([1.0, 1.0 if echo_ok else 0.0, 1.0], np.float32))
        b["gray"].append(gray)
        b["ab"].append(ab)
        b["inv_depth"].append(zeros_depth)
        b["depth_valid"].append(zeros_depth)       # no depth sensor on the node
        n_used[split] += 1
        if len(b["gray"]) >= SHARD:
            counters[split] = _flush(b, out / split, counters[split])

    print()
    for split in splits:
        counters[split] = _flush(bufs[split], out / split, counters[split])
        print(f"{split}: {n_used[split]} samples -> {counters[split]} shards "
              f"in {out / split}")
    n_all = sum(echo_state.values())
    print()
    print(f"echo: {echo_state['ok']}/{n_all} samples usable")
    if echo_state["old"]:
        print(f"  {echo_state['old']} from captures made before the echo fix - their "
              f"window never contained the chirp, so echo is masked off (mask[1]=0) "
              f"for them. Thermal and sonar from those samples are still used.")
    if echo_state["unheard"]:
        print(f"  WARNING: {echo_state['unheard']} sample(s) where the node did not hear "
              f"its own chirp (echoOnset -1) - masked off. Many of these means the "
              f"speaker or amp is not producing sound.")
    if n_used["val"] == 0:
        print("\nWARNING: no val samples. Capture more scenes, or name val "
              "scenes explicitly with --held-out-scenes.")
    if args.r_use is not None:
        print(f"\nrange buckets (r_use={args.r_use} m): "
              + ", ".join(f"{k}={v}" for k, v in sorted(bucket_counts.items())))
        if bucket_counts.get("beyond"):
            print(f"'stress' split ({bucket_counts['beyond']} samples) is "
                  f"held out of train/val entirely - evaluate it separately "
                  f"as a graceful-degradation result, not folded into the "
                  f"headline metric.")
    if args.baa_max_range is not None:
        print(f"\nBAB (thermalFar) used for {used_far} sample(s) beyond "
              f"{args.baa_max_range} m")
        if far_fallbacks:
            n_bad = sum(far_fallbacks.values())
            print(f"WARNING: {n_bad} sample(s) across {len(far_fallbacks)} "
                  f"scene(s) needed BAB but its frame was missing or marked "
                  f"NOT FOUND - fell back to BAA for those, which is exactly "
                  f"the low-detail-at-distance reading --baa-max-range exists "
                  f"to avoid: {sorted(far_fallbacks)[:10]}"
                  + (" ..." if len(far_fallbacks) > 10 else ""))


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
