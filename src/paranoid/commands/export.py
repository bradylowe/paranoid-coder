"""Export summaries to JSON or CSV."""

from __future__ import annotations

import csv
import json
import sys
from argparse import Namespace
from pathlib import Path

from paranoid.config import require_project_root
from paranoid.storage import SQLiteStorage, Summary


def _summary_to_dict(s: Summary) -> dict:
    """Convert Summary to a JSON-serializable dict."""
    return {
        "path": s.path,
        "type": s.type,
        "hash": s.hash,
        "description": s.description,
        "file_extension": s.file_extension,
        "error": s.error,
        "needs_update": s.needs_update,
        "model": s.model,
        "model_version": s.model_version,
        "prompt_version": s.prompt_version,
        "context_level": s.context_level,
        "generated_at": s.generated_at,
        "updated_at": s.updated_at,
        "tokens_used": s.tokens_used,
        "generation_time_ms": s.generation_time_ms,
    }


def _export_json(summaries: list[Summary], out: object) -> None:
    """Write summaries as JSON array to out (e.g. sys.stdout)."""
    data = [_summary_to_dict(s) for s in summaries]
    json.dump(data, out, indent=2)


def _export_csv(summaries: list[Summary], out: object) -> None:
    """Write summaries as flat CSV to out (e.g. sys.stdout)."""
    fieldnames = [
        "path",
        "type",
        "hash",
        "description",
        "file_extension",
        "error",
        "needs_update",
        "model",
        "model_version",
        "prompt_version",
        "context_level",
        "generated_at",
        "updated_at",
        "tokens_used",
        "generation_time_ms",
    ]
    writer = csv.DictWriter(out, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for s in summaries:
        row = _summary_to_dict(s)
        # CSV: normalize None to empty string, bool to true/false
        for k, v in row.items():
            if v is None:
                row[k] = ""
            elif isinstance(v, bool):
                row[k] = "true" if v else "false"
        writer.writerow(row)


def run(args: Namespace) -> None:
    """Run the export command."""
    path: Path = getattr(args, "path", Path("."))
    project_root = require_project_root(path)
    fmt = getattr(args, "format", "json")

    scope_path = path.resolve().as_posix()
    storage = SQLiteStorage(project_root)
    with storage:
        summaries = storage.get_all_summaries(scope_path=scope_path)

    if fmt == "json":
        _export_json(summaries, sys.stdout)
    else:
        _export_csv(summaries, sys.stdout)
