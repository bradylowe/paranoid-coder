"""Show summary statistics."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

from pathspec import PathSpec

from paranoid.config import load_config, require_project_root
from paranoid.storage import SQLiteStorage, ProjectStats
from paranoid.utils.ignore import build_spec, is_ignored, load_patterns


def _count_summarizable(
    root_path: Path,
    project_root: Path,
    spec: PathSpec,
) -> tuple[int, int]:
    """
    Count files and directories under root_path that would be summarized (not ignored).
    Does not read file contents. Returns (file_count, dir_count).
    """
    root_path = root_path.resolve()
    project_root = project_root.resolve()
    file_count = 0
    dir_count = 0

    if root_path.is_file():
        if is_ignored(root_path, project_root, spec):
            return (0, 0)
        return (1, 0)

    if not root_path.is_dir():
        return (0, 0)

    def recurse(current: Path) -> None:
        nonlocal file_count, dir_count
        try:
            entries = list(current.iterdir())
        except OSError:
            return
        for entry in sorted(entries, key=lambda p: p.name):
            if entry.is_file():
                if is_ignored(entry, project_root, spec):
                    continue
                file_count += 1
            else:
                if is_ignored(entry, project_root, spec):
                    continue
                recurse(entry)
                dir_count += 1
        return

    recurse(root_path)
    if not is_ignored(root_path, project_root, spec):
        dir_count += 1

    return (file_count, dir_count)


def _format_timestamp(iso_str: str | None) -> str:
    """Return a short human-readable timestamp, or 'never' if None."""
    if not iso_str:
        return "never"
    try:
        # Keep first 19 chars for "YYYY-MM-DDTHH:MM:SS", drop T and use space for display
        return iso_str.replace("T", " ")[:19]
    except Exception:
        return iso_str or "never"


def _print_stats(
    stats: ProjectStats,
    total_files: int,
    total_dirs: int,
    scope_label: str,
) -> None:
    """Print stats to stdout."""
    summarized_files = stats.count_by_type.get("file", 0)
    summarized_dirs = stats.count_by_type.get("directory", 0)
    summarized_total = summarized_files + summarized_dirs
    total_items = total_files + total_dirs
    coverage_pct = (100.0 * summarized_total / total_items) if total_items > 0 else 0.0

    print(f"Summary statistics {scope_label}")
    print()
    print("  By type:")
    print(f"    files:      {summarized_files}")
    print(f"    directories: {summarized_dirs}")
    print(f"    total:      {summarized_total}")
    print()
    if stats.language_breakdown:
        print("  By language:")
        for lang, count in stats.language_breakdown:
            display_name = lang.replace("-", " ").title() if lang else "Unknown"
            print(f"    {display_name}: {count} files")
    else:
        print("  By language: (no file summaries)")
    print()
    print("  Coverage:")
    print(f"    summarized: {summarized_total} / {total_items} (files + dirs in scope)")
    print(f"    percentage: {coverage_pct:.1f}%")
    print()
    print(f"  Last update:  {_format_timestamp(stats.last_updated_at)}")
    print()
    if stats.model_breakdown:
        print("  Model usage:")
        for model, count in stats.model_breakdown:
            print(f"    {model}: {count}")
    else:
        print("  Model usage: (none)")


def run(args: Namespace) -> None:
    """Run the stats command."""
    path: Path = getattr(args, "path", Path("."))
    project_root = require_project_root(path)

    config = load_config(project_root)
    patterns_with_source = load_patterns(project_root, config)
    patterns = [p for p, _ in patterns_with_source]
    spec = build_spec(patterns)

    total_files, total_dirs = _count_summarizable(path, project_root, spec)
    scope_path_posix = path.resolve().as_posix()
    scope_label = f"(scope: {scope_path_posix})"

    storage = SQLiteStorage(project_root)
    with storage:
        for msg in storage.get_migration_messages():
            print(f"Note: {msg}", file=sys.stderr)
        stats = storage.get_stats(scope_path=scope_path_posix)
        _print_stats(stats, total_files, total_dirs, scope_label)
