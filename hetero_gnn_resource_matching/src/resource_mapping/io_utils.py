"""I/O helpers for JSON, YAML and reproducibility."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import yaml


def load_json(path: str | Path) -> Any:
    """Load a JSON file."""

    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data: Any, path: str | Path) -> None:
    """Save data as pretty JSON."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML config."""

    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_path(base_dir: str | Path, path: str | Path) -> Path:
    """Resolve a possibly relative project path."""

    p = Path(path)
    return p if p.is_absolute() else Path(base_dir) / p


def set_seed(seed: int) -> None:
    """Seed Python, NumPy and PyTorch."""

    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ModuleNotFoundError:
        pass


def get_device(name: str):
    """Return a torch device from config value."""

    import torch

    if name == "cuda_if_available":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(name)
