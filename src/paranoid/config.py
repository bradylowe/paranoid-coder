"""Configuration: default paths, constants, and config loading (global + project overrides)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Directory name inside a target project for Paranoid storage
PARANOID_DIR = ".paranoid-coder"
SUMMARIES_DB = "summaries.db"
CONFIG_FILENAME = "config.json"

# Global config location
def _global_config_dir() -> Path:
    return Path.home() / ".paranoid"


def global_config_path() -> Path:
    """Path to global config file (~/.paranoid/config.json)."""
    return _global_config_dir() / CONFIG_FILENAME


def default_config() -> dict[str, Any]:
    """Default configuration matching project_plan.md."""
    return {
        "default_model": "qwen2.5-coder:7b",
        "ollama_host": "http://localhost:11434",
        "viewer": {
            "theme": "light",
            "font_size": 10,
            "show_ignored": False,
        },
        "logging": {
            "level": "INFO",
            "file": str(Path("~/.paranoid/paranoid.log").expanduser()),
        },
        "ignore": {
            "use_gitignore": True,
            "builtin_patterns": [".git/", ".paranoid-coder/"],
            "additional_patterns": [],
        },
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    """Load JSON from path; return None if file missing or invalid."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except (json.JSONDecodeError, OSError):
        return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override into base recursively. Mutates base; returns base."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_global_config() -> dict[str, Any]:
    """Load global config from ~/.paranoid/config.json. Returns defaults if missing."""
    path = global_config_path()
    data = _load_json(path)
    if data is None:
        return default_config()
    return _deep_merge(default_config(), data)


def project_config_path(project_root: Path) -> Path:
    """Path to project-local config (<project>/.paranoid-coder/config.json)."""
    return project_root / PARANOID_DIR / CONFIG_FILENAME


def load_config(project_root: Path | None = None) -> dict[str, Any]:
    """
    Load merged configuration: defaults + global (~/.paranoid/config.json) + project overrides.

    If project_root is None, only global config (and defaults) are used.
    Project overrides apply when project_root is set and .paranoid-coder/config.json exists.
    """
    merged = load_global_config()
    if project_root is not None:
        path = project_config_path(project_root.resolve())
        project_data = _load_json(path)
        if project_data is not None:
            _deep_merge(merged, project_data)
    return merged


def get_project_root(path: Path) -> Path:
    """
    Resolve path to absolute. If it is a file, use its parent.
    Does not search upward for .paranoid-coder; that is done when opening storage.
    """
    resolved = path.resolve()
    if resolved.is_file():
        return resolved.parent
    return resolved


def resolve_path(path: Path) -> Path:
    """Resolve path to absolute, normalized."""
    return path.resolve()


def find_project_root(path: Path) -> Path | None:
    """
    Walk upward from path looking for a directory that contains .paranoid-coder.
    Returns that directory if found, else None. Use this for all commands except init.
    """
    resolved = path.resolve()
    if resolved.is_file():
        resolved = resolved.parent
    current: Path | None = resolved
    while current is not None:
        if (current / PARANOID_DIR).is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def require_project_root(path: Path) -> Path:
    """
    Return the project root (directory containing .paranoid-coder) for path.
    If not found, print an error and exit. Use for all commands except init.
    """
    root = find_project_root(path)
    if root is None:
        print(
            "No paranoid project initialized. Run 'paranoid init' in the project directory first.",
            file=sys.stderr,
        )
        sys.exit(1)
    return root.resolve()
