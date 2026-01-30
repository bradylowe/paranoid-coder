"""Clean stale or ignored summaries."""

from __future__ import annotations

import sys
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from paranoid.config import load_config, require_project_root
from paranoid.storage import SQLiteStorage
from paranoid.utils.ignore import build_spec, is_ignored, load_patterns


def _parse_updated_at(updated_at: str) -> datetime | None:
    """Parse ISO timestamp; return None if invalid. Handles 'Z' for Python 3.10."""
    if not updated_at:
        return None
    s = updated_at.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def run(args: Namespace) -> None:
    """Run the clean command: remove summaries by --pruned, --stale, or --model.
    If path is a subpath of the project, only summaries under that path are considered.
    """
    project_root = require_project_root(args.path)
    scope_path = Path(args.path).resolve().as_posix()
    pruned = getattr(args, "pruned", False)
    stale = getattr(args, "stale", False)
    model = getattr(args, "model", None)
    days = getattr(args, "days", 30)
    dry_run = getattr(args, "dry_run", False)

    if not (pruned or stale or model):
        print(
            "Error: specify at least one of --pruned, --stale, or --model.",
            file=sys.stderr,
        )
        sys.exit(1)

    config = load_config(project_root)
    storage = SQLiteStorage(project_root)
    storage._connect()

    # Only consider summaries at or under the given path (project root or subpath)
    summaries = storage.get_all_summaries(scope_path=scope_path)

    to_delete: set[str] = set()

    if pruned:
        patterns_with_source = load_patterns(project_root, config)
        patterns = [p for p, _ in patterns_with_source]
        spec = build_spec(patterns)
        for summary in summaries:
            if is_ignored(Path(summary.path), project_root, spec):
                to_delete.add(summary.path)

    if stale:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        for summary in summaries:
            dt = _parse_updated_at(summary.updated_at)
            if dt is not None and dt < cutoff:
                to_delete.add(summary.path)

    if model:
        for summary in summaries:
            if summary.model == model:
                to_delete.add(summary.path)

    if not to_delete:
        print("No summaries to remove.")
        storage.close()
        return

    if dry_run:
        print(f"Would delete {len(to_delete)} summar{'y' if len(to_delete) == 1 else 'ies'}:")
        sorted_paths = sorted(to_delete)
        for path in sorted_paths[:20]:
            print(f"  {path}")
        if len(sorted_paths) > 20:
            print(f"  ... and {len(sorted_paths) - 20} more")
        storage.close()
        return

    for path in to_delete:
        storage.delete_summary(path)
    storage.close()
    print(f"Deleted {len(to_delete)} summar{'y' if len(to_delete) == 1 else 'ies'}.")
