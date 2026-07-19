"""Create and load portable model bundles.

A bundle is a zip file containing everything needed to serve NOVISNet on
another machine without cloning the repository:

  config.yaml     flattened, resolved config (no ``inherit:`` chain)
  weights.pt      EMA model weights (the ``best.pt`` format)
  metadata.json   parameter count, device, export timestamp, git hash

Usage from code:
    from novis.server.bundle import create_bundle, load_bundle
    create_bundle(service, Path("novis_bundle.zip"))
    config_path, ckpt_path = load_bundle(Path("novis_bundle.zip"))

Usage from CLI:
    python bundle_cli.py --config ... --ckpt ... --out novis_bundle.zip
    python bundle_cli.py --load novis_bundle.zip --serve
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import torch
import yaml

from novis.config import namespace_to_dict


def _git_hash() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5)
        if out.returncode == 0:
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def create_bundle(service, out_path: Path) -> Path:
    """Package the current model state into a portable zip bundle.

    Args:
        service: a running InferenceService instance.
        out_path: where to write the zip file.

    Returns:
        The path to the created zip file.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Flatten config to a plain dict (no inherit chain).
    cfg_dict = namespace_to_dict(service.cfg)

    # Model weights: prefer continual checkpoint if available, then EMA.
    if service._continual is not None:
        weights = service._continual.shadow
        source = "continual"
    else:
        weights = service.model.state_dict()
        source = service.ckpt_path or "untrained"

    metadata = {
        "name": "NOVISNet",
        "params_m": round(service.model.param_count() / 1e6, 2),
        "out_hw": list(service.out_hw),
        "device_exported_on": service.device,
        "checkpoint_source": source,
        "trained": service.trained,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "git_hash": _git_hash(),
    }
    if service._continual is not None:
        metadata["continual_corrections"] = service._continual.corrections

    # Write everything to a temporary directory, then zip.
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        with open(tmp / "config.yaml", "w", encoding="utf-8") as f:
            yaml.dump(cfg_dict, f, default_flow_style=False, sort_keys=False)
        torch.save({"model": weights}, tmp / "weights.pt")
        with open(tmp / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in tmp.iterdir():
                zf.write(p, p.name)

    return out_path


def load_bundle(zip_path: Path, extract_to: Path | None = None
                ) -> tuple[Path, Path]:
    """Extract a bundle and return (config_path, ckpt_path).

    Args:
        zip_path: path to the zip bundle.
        extract_to: directory to extract into. If None, a temporary directory
            is used (caller must manage its lifetime).

    Returns:
        (config_path, ckpt_path) ready for InferenceService or run.py.
    """
    zip_path = Path(zip_path)
    if extract_to is None:
        extract_to = Path(tempfile.mkdtemp(prefix="novis_bundle_"))
    else:
        extract_to = Path(extract_to)
        extract_to.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

    config_path = extract_to / "config.yaml"
    ckpt_path = extract_to / "weights.pt"
    meta_path = extract_to / "metadata.json"

    if not config_path.exists() or not ckpt_path.exists():
        raise FileNotFoundError(
            f"Bundle is missing config.yaml or weights.pt in {extract_to}")

    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        print(f"loaded bundle: {meta.get('name', '?')} "
              f"({meta.get('params_m', '?')}M params, "
              f"exported {meta.get('exported_at', '?')})")

    return config_path, ckpt_path
