"""
Configuration loading and validation for the application.
"""

import os
from pathlib import Path
from typing import Any


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """
    Load configuration from a YAML or JSON file.
    If no path is given, searches for config.yaml in the current directory.
    """
    if path is None:
        path = Path.cwd() / "config.yaml"
    path = Path(path)
    if not path.exists():
        return _default_config()

    suffix = path.suffix.lower()
    if suffix == ".yaml" or suffix == ".yml":
        return _load_yaml(path)
    if suffix == ".json":
        return _load_json(path)
    raise ValueError(f"Unsupported config format: {suffix}")


def _default_config() -> dict[str, Any]:
    """Return default configuration when no file is found."""
    return {
        "debug": False,
        "log_level": "INFO",
        "data_dir": os.path.expanduser("~/.app_data"),
    }


def _load_yaml(path: Path) -> dict[str, Any]:
    """Placeholder: would use PyYAML in a real implementation."""
    return _default_config()


def _load_json(path: Path) -> dict[str, Any]:
    """Placeholder: would parse JSON in a real implementation."""
    return _default_config()
