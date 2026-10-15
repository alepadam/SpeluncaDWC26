"""Load config.yaml (+ private overrides from .env) and resolve project paths."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV_DATA_DIR = "DWC26_DATA_DIR"


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None = None, root: str | Path | None = None,
                overrides: dict | None = None, use_env: bool = True) -> dict[str, Any]:
    """Read config.yaml, apply `overrides` (used by tests), then .env, and return absolute paths.

    - `root` points the whole pipeline at another folder (tests use a temporary one).
    - If .env (or the environment) sets DWC26_DATA_DIR, it replaces paths.raw.
    """
    root = Path(root) if root else ROOT
    cfg_path = Path(path) if path else root / "config.yaml"
    with open(cfg_path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if overrides:
        cfg = _deep_merge(cfg, overrides)

    paths = {k: (root / v) for k, v in cfg["paths"].items()}
    if use_env:
        load_dotenv(root / ".env", override=False)
        data_dir = os.environ.get(ENV_DATA_DIR, "").strip()
        if data_dir:
            paths["raw"] = Path(data_dir).expanduser()
    if not paths["raw"].is_dir():
        raise FileNotFoundError(f"Data folder not found: {paths['raw']} (set {ENV_DATA_DIR} in .env)")
    for key, p in paths.items():
        if key != "raw":
            p.mkdir(parents=True, exist_ok=True)

    cfg["root"] = root
    cfg["paths"] = paths
    return cfg


def find_raw_file(cfg: dict, name: str) -> Path:
    """Locate a dataset file by exact name anywhere under the raw folder (handles dwc26/TestCases/...)."""
    raw = cfg["paths"]["raw"]
    direct = raw / name
    if direct.is_file():
        return direct
    matches = sorted(p for p in raw.rglob(name) if p.is_file())
    if not matches:
        raise FileNotFoundError(f"{name!r} not found under {raw}")
    if len(matches) > 1:
        raise FileExistsError(f"{name!r} found more than once under {raw}: {matches}")
    return matches[0]
