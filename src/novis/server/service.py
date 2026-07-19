"""Model-serving core for the browser interface.

Loads NOVISNet once, generates demo scenes, runs inference, and renders
sensor inputs and reconstructions as base64 PNGs. All heavy state lives in
one InferenceService instance shared by the FastAPI app.
"""

from __future__ import annotations

import math
import threading
import time
from pathlib import Path

import numpy as np
import torch

from novis.config import load_config, namespace_to_dict
from novis.data import SyntheticNOVISDataset
from novis.data import degradation as D
from novis.models import build_model

from .render import blackbody, ocean, to_png_b64, turbo

ROOT = Path(__file__).resolve().parents[3]          # NOVIS_Model/
LOGVAR_MIN, LOGVAR_MAX = -6.0, 4.0
N_DEMO_SAMPLES = 8


def _candidate_checkpoints() -> list[Path]:
    """best.pt across runs, fusion stage first, then newest first."""
    ckpts = sorted((ROOT / "checkpoints").glob("*/best.pt"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return ([p for p in ckpts if "fusion" in p.parent.name]
            + [p for p in ckpts if "fusion" not in p.parent.name])


class InferenceService:
    def __init__(self, config: str = "configs/base.yaml",
                 ckpt: str | None = None, device: str | None = None):
        self.config_path = str(config)
        self.cfg = load_config(str(ROOT / config) if not Path(config).is_absolute()
                               else config)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.out_hw = tuple(self.cfg.data.out_hw)
        self.model = build_model(self.cfg)

        self.ckpt_path = None
        self.trained = False
        candidates = ([Path(ckpt)] if ckpt else _candidate_checkpoints())
        for p in candidates:
            if not p.exists():
                continue
            try:
                state = torch.load(p, map_location="cpu", weights_only=True)
                self.model.load_state_dict(state["model"])
                del state
                self.ckpt_path = str(p)
                self.trained = True
                break
            except RuntimeError:
                # Checkpoint from a differently sized config; keep looking.
                if ckpt:
                    raise
        self.model.to(self.device).eval()
        self._lock = threading.Lock()
        self._demo = SyntheticNOVISDataset(n=N_DEMO_SAMPLES,
                                           out_hw=self.out_hw, seed=7000)

    # ------------------------------------------------------------- info

    def model_info(self) -> dict:
        m = self.cfg.model
        return {
            "name": "NOVISNet",
            "params_m": round(self.model.param_count() / 1e6, 2),
            "dim": m.dim, "depth": m.depth, "heads": m.heads,
            "ffn_ratio": getattr(m, "ffn_ratio", 3),
            "decoder_chs": list(m.decoder_chs),
            "color_head": bool(getattr(m, "color_head", True)),
            "out_hw": list(self.out_hw),
            "grid_hw": list(self.model.grid_hw),
            "tokens": {"thermal": 192, "echo": 24, "sonar": 4},
            "device": self.device,
            "device_name": (torch.cuda.get_device_name(0)
                            if self.device == "cuda" else "CPU"),
            "checkpoint": self.ckpt_path,
            "trained": self.trained,
            "config": self.config_path,
            "config_dump": namespace_to_dict(self.cfg),
        }

    # ---------------------------------------------------------- samples

    def demo_sample(self, sample_id: int | None = None,
                    seed: int | None = None) -> dict:
        if seed is not None:
            ds = SyntheticNOVISDataset(n=1, out_hw=self.out_hw, seed=seed)
            return ds[0]
        return self._demo[int(sample_id or 0) % N_DEMO_SAMPLES]

    def sample_summaries(self) -> list[dict]:
        out = []
        for i in range(N_DEMO_SAMPLES):
            s = self._demo[i]
            out.append({
                "id": i,
                "thermal_png": to_png_b64(blackbody(s["thermal"][0]), scale=4),
                "near_m": round(
                    float(D.inv01_to_depth(s["inv_depth"][0]).min()), 2),
            })
        return out

    # -------------------------------------------------------- rendering

    @staticmethod
    def render_inputs(sample: dict) -> dict:
        sonar = sample["sonar"]
        return {
            "thermal_png": to_png_b64(blackbody(sample["thermal"][0]), scale=8),
            "echo_png": to_png_b64(ocean(sample["echo"][0]), scale=4),
            "sonar": {
                "left_m": round(float(sonar[0]) * D.SONAR_MAX_M, 2),
                "right_m": round(float(sonar[1]) * D.SONAR_MAX_M, 2),
                "left_valid": bool(sonar[2] > 0.5),
                "right_valid": bool(sonar[3] > 0.5),
                "max_m": D.SONAR_MAX_M,
            },
            "mask": [bool(v > 0.5) for v in sample["mask"]],
        }

    def render_truth(self, sample: dict) -> dict:
        return {
            "gray_png": to_png_b64(sample["gray"][0]),
            "depth_png": to_png_b64(turbo(sample["inv_depth"][0])),
        }

    # -------------------------------------------------------- inference

    def infer(self, sample: dict, mask_override=None) -> dict:
        dev = self.device
        to = lambda a: torch.from_numpy(np.ascontiguousarray(a)).unsqueeze(0).to(dev)
        mask = np.asarray(mask_override, np.float32) if mask_override is not None \
            else sample["mask"]
        t0 = time.perf_counter()
        with self._lock, torch.no_grad():
            out = self.model(to(sample["thermal"]), to(sample["echo"]),
                             to(sample["sonar"]), to(mask))
            if dev == "cuda":
                torch.cuda.synchronize()
        ms = (time.perf_counter() - t0) * 1000.0
        out = {k: v[0].float().cpu().numpy() for k, v in out.items()}

        gray = out["gray"][0]
        inv = out["inv_depth"][0]
        depth_m = D.inv01_to_depth(inv)
        result = {
            "gray_png": to_png_b64(gray),
            "depth_png": to_png_b64(turbo(inv)),
            "depth_min_m": round(float(depth_m.min()), 2),
            "depth_max_m": round(float(depth_m.max()), 2),
            "latency_ms": round(ms, 1),
            "has_color": "ab" in out,
        }
        if "ab" in out:
            ab = out["ab"].transpose(1, 2, 0)
            rgb = D.lab_to_rgb(gray, ab)
            conf = (LOGVAR_MAX - out["log_var"][0]) / (LOGVAR_MAX - LOGVAR_MIN)
            conf = np.clip(conf, 0.0, 1.0)
            result["color_png"] = to_png_b64(rgb)
            # Grayscale confidence PNG; the client gates color with it.
            result["conf_png"] = to_png_b64(conf)
            result["conf_mean"] = round(float(conf.mean()), 3)
        return result

    # ------------------------------------------------------- live demo

    def animated_sample(self, t: float) -> dict:
        """Smoothly animated scene for the live stream (no dataset reads)."""
        H, W = self.out_hw
        rng = np.random.default_rng(int(t * 997) % 100000)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        gray = 0.25 + 0.3 * (xx / W)
        depth_m = 2.0 + 5.0 * (1.0 - yy / H)
        temp = np.full((H, W), 0.25, np.float32)
        ab = np.zeros((H, W, 2), np.float32)

        # Two warm objects on smooth orbits.
        paths = [(0.30 + 0.22 * math.sin(t * 0.9),
                  0.55 + 0.25 * math.cos(t * 0.7), 0.55, (0.35, -0.15)),
                 (0.62 + 0.18 * math.sin(t * 0.5 + 2.0),
                  0.35 + 0.20 * math.sin(t * 1.1 + 1.0), 0.80, (-0.2, 0.3))]
        for cx, cy, warm, col in paths:
            w = int(W * 0.18)
            h = int(H * 0.30)
            x0 = int(np.clip(cx * W - w / 2, 0, W - w))
            y0 = int(np.clip(cy * H - h / 2, 0, H - h))
            d = 1.5 + 2.0 * (0.5 + 0.5 * math.sin(t * 0.8 + cx * 6.0))
            sl = (slice(y0, y0 + h), slice(x0, x0 + w))
            gray[sl] = 0.45 + warm * 0.3
            depth_m[sl] = np.minimum(depth_m[sl], d)
            temp[sl] = warm
            ab[sl] = col

        gray = np.clip(gray + 0.03 * rng.standard_normal((H, W)), 0, 1)
        thermal = D.degrade_thermal(temp, rng)
        echo = rng.random((2, 64, 64)).astype(np.float32) * 0.15
        near = float(depth_m.min())
        row = int(np.clip(near / 8.0 * 63, 0, 63))
        echo[:, row: row + 3, :] += 0.7
        ranges, valid = D.synth_sonar(depth_m, hfov_deg=55.0, rng=rng)
        sonar = np.zeros(10, np.float32)
        sonar[0:2], sonar[2:4] = ranges, valid
        sonar[4:8] = ranges.mean()
        return {
            "thermal": thermal[None].astype(np.float32),
            "echo": np.clip(echo, 0, 1),
            "sonar": sonar,
            "mask": np.ones(3, np.float32),
            "gray": gray[None].astype(np.float32),
            "ab": ab.transpose(2, 0, 1).astype(np.float32),
            "inv_depth": D.depth_to_inv01(depth_m)[None],
            "depth_valid": np.ones((1, H, W), np.float32),
        }

    # ----------------------------------------------------------- runs

    @staticmethod
    def list_runs() -> list[dict]:
        runs = []
        for log in sorted((ROOT / "checkpoints").glob("*/log.csv")):
            import csv as csvmod
            with open(log, newline="", encoding="utf-8") as f:
                rows = list(csvmod.DictReader(f))
            if not rows:
                continue
            runs.append({
                "name": log.parent.name,
                "epochs": len(rows),
                "columns": list(rows[0].keys()),
                "rows": [{k: _num(v) for k, v in r.items()} for r in rows],
                "has_best": (log.parent / "best.pt").exists(),
            })
        return runs

    @staticmethod
    def results_metrics() -> dict | None:
        import json
        p = ROOT / "results" / "metrics.json"
        if not p.exists():
            return None
        with open(p, encoding="utf-8") as f:
            return json.load(f)


def _num(v: str):
    try:
        f = float(v)
        return int(f) if f.is_integer() and abs(f) < 1e9 else f
    except (TypeError, ValueError):
        return v
