"""YAML config loading with base-config inheritance."""

from pathlib import Path
from types import SimpleNamespace

import yaml


def _to_namespace(obj):
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_to_namespace(v) for v in obj]
    return obj


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str) -> SimpleNamespace:
    """Load a YAML config. If it has an `inherit:` key, merge onto that file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    parent = cfg.pop("inherit", None)
    if parent:
        parent_path = (path.parent / parent).resolve()
        with open(parent_path, "r", encoding="utf-8") as f:
            base = yaml.safe_load(f) or {}
        base.pop("inherit", None)
        cfg = _deep_merge(base, cfg)
    return _to_namespace(cfg)


def namespace_to_dict(ns) -> dict:
    if isinstance(ns, SimpleNamespace):
        return {k: namespace_to_dict(v) for k, v in vars(ns).items()}
    if isinstance(ns, list):
        return [namespace_to_dict(v) for v in ns]
    return ns
