"""List or edit prompt templates (CLI command)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

from paranoid.config import PARANOID_DIR, PROMPT_OVERRIDES_FILENAME, require_project_root
from paranoid.llm.prompts import get_builtin_template, get_prompt_keys


def _overrides_path(project_root: Path) -> Path:
    return project_root / PARANOID_DIR / PROMPT_OVERRIDES_FILENAME


def _load_overrides(project_root: Path) -> dict[str, str]:
    path = _overrides_path(project_root)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if isinstance(v, str)}
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_overrides(project_root: Path, overrides: dict[str, str]) -> None:
    path = _overrides_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overrides, indent=2), encoding="utf-8")


def _run_list(project_root: Path) -> None:
    overrides = _load_overrides(project_root)
    keys = get_prompt_keys()
    valid_keys = {f"{lang}:{kind}" for lang, kind in keys}
    # Show built-in keys first; then any override-only keys
    all_keys = sorted(set(valid_keys) | set(overrides))
    print("Prompt templates (language:kind)")
    print()
    for key in all_keys:
        source = "overridden" if key in overrides else "built-in"
        print(f"  {key:<30} {source}")
    print()
    print("Placeholders:")
    print("  file:      {filename} {content} {existing} {length} {extension}")
    print("  directory: {dir_path} {children} {existing} {n_paragraphs}")


def _run_edit(project_root: Path, name: str) -> None:
    # name is e.g. "python:file" or "javascript:directory"
    if ":" not in name:
        print(f"Error: Prompt name must be 'language:kind' (e.g. python:file). Got: {name}", file=sys.stderr)
        sys.exit(1)
    lang, kind = name.split(":", 1)
    kind = kind.strip().lower()
    if kind not in ("file", "directory"):
        print(f"Error: Kind must be 'file' or 'directory'. Got: {kind}", file=sys.stderr)
        sys.exit(1)
    key = f"{lang}:{kind}"
    valid_keys = {f"{l}:{k}" for l, k in get_prompt_keys()}
    if key not in valid_keys and key not in _load_overrides(project_root):
        # Allow custom keys (e.g. mylang:file) so users can add new languages
        pass
    overrides = _load_overrides(project_root)
    current = overrides.get(key) or get_builtin_template(lang, kind) or ""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor and sys.platform == "win32":
        editor = "notepad"
    if not editor:
        editor = "nano" if os.path.exists("/usr/bin/nano") else "vi"
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(current)
        tmp_path = f.name
    try:
        subprocess.run([editor, tmp_path], check=False)
        new_content = Path(tmp_path).read_text(encoding="utf-8")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    if new_content.strip() == "":
        # Remove override to fall back to built-in
        overrides.pop(key, None)
        print(f"Cleared override for {key}; will use built-in template.")
    else:
        overrides[key] = new_content
    _save_overrides(project_root, overrides)
    print(f"Saved prompt: {key}")


def run(args: Namespace) -> None:
    """Run the prompts command (list or edit)."""
    path: Path = getattr(args, "path", Path(".")).resolve()
    project_root = require_project_root(path)
    edit_name = getattr(args, "edit", None)
    if edit_name is not None:
        _run_edit(project_root, edit_name)
    else:
        _run_list(project_root)
