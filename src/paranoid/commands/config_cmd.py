"""Show or edit configuration (CLI command)."""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from paranoid.config import (
    find_project_root,
    global_config_path,
    load_config,
    project_config_path,
    save_config,
)


def _get_nested_key(data: dict[str, Any], key_path: str) -> Any:
    """Return value at dotted key (e.g. 'ignore.additional_patterns'); None if missing."""
    parts = key_path.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested_key(data: dict[str, Any], key_path: str, value: Any) -> None:
    """Set a nested key (e.g. 'viewer.theme') in data; create intermediate dicts if needed."""
    parts = key_path.split(".")
    current: dict[str, Any] = data
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _parse_set_value(value_str: str) -> Any:
    """Parse KEY=VALUE value: try JSON (number, bool, quoted string), else use as string."""
    value_str = value_str.strip()
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        return value_str


def _load_target_config(target_path: Path) -> dict[str, Any]:
    """Load raw config from target path; return {} if missing or invalid."""
    if not target_path.is_file():
        return {}
    try:
        text = target_path.read_text(encoding="utf-8")
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def run(args: Namespace) -> None:
    """Run the config command: show merged settings or set/add/remove values (global or project-local)."""
    show = getattr(args, "show", False)
    set_key = getattr(args, "set_key", None)
    add_key = getattr(args, "add_key", None)
    remove_key = getattr(args, "remove_key", None)
    path = getattr(args, "path", Path("."))
    use_global = getattr(args, "global_", False)

    if not show and not set_key and not add_key and not remove_key:
        print(
            "Error: specify --show, --set KEY=VALUE, --add KEY VALUE, or --remove KEY VALUE.",
            file=sys.stderr,
        )
        sys.exit(1)

    project_root = find_project_root(Path(path).resolve())

    def _target_path_and_label() -> tuple[Path, str]:
        if use_global or project_root is None:
            return global_config_path(), "global"
        return project_config_path(project_root), f"project ({project_root.as_posix()})"

    if set_key:
        if "=" not in set_key:
            print("Error: --set requires KEY=VALUE (e.g. default_model=qwen2.5-coder:7b).", file=sys.stderr)
            sys.exit(1)
        key_str, _, value_str = set_key.partition("=")
        key_str = key_str.strip()
        if not key_str:
            print("Error: empty key in KEY=VALUE.", file=sys.stderr)
            sys.exit(1)
        value = _parse_set_value(value_str)

        target_path, source_label = _target_path_and_label()
        existing = _load_target_config(target_path)
        _set_nested_key(existing, key_str, value)
        save_config(target_path, existing)
        print(f"Set {key_str} = {json.dumps(value)} in {source_label} config.")

    if add_key:
        key_str, value_str = add_key[0].strip(), add_key[1].strip()
        if not key_str:
            print("Error: empty key in --add KEY VALUE.", file=sys.stderr)
            sys.exit(1)
        target_path, source_label = _target_path_and_label()
        existing = _load_target_config(target_path)
        current = _get_nested_key(existing, key_str)
        if not isinstance(current, list):
            current = []
        current.append(value_str)
        _set_nested_key(existing, key_str, current)
        save_config(target_path, existing)
        print(f"Added {json.dumps(value_str)} to {key_str} in {source_label} config.")

    if remove_key:
        key_str, value_str = remove_key[0].strip(), remove_key[1].strip()
        if not key_str:
            print("Error: empty key in --remove KEY VALUE.", file=sys.stderr)
            sys.exit(1)
        target_path, source_label = _target_path_and_label()
        existing = _load_target_config(target_path)
        current = _get_nested_key(existing, key_str)
        if isinstance(current, list):
            current = [x for x in current if x != value_str]
        else:
            current = []
        _set_nested_key(existing, key_str, current)
        save_config(target_path, existing)
        print(f"Removed {json.dumps(value_str)} from {key_str} in {source_label} config.")

    if show:
        config = load_config(project_root)
        source_note = "defaults + global"
        if project_root is not None:
            source_note += f" + project ({project_root.as_posix()})"
        print(f"# Config: {source_note}")
        print(json.dumps(config, indent=2))
