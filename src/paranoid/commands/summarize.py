"""Core summarization logic (tree walk, Ollama, progress)."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from pathspec import PathSpec

from paranoid.config import load_config, require_project_root
from paranoid.llm import (
    ContextOverflowException,
    OllamaConnectionError,
    PROMPT_VERSION,
    detect_directory_language,
    detect_language,
    summarize_directory as llm_summarize_directory,
    summarize_file as llm_summarize_file,
)
from paranoid.storage import SQLiteStorage, Summary
from paranoid.utils.hashing import content_hash, needs_summarization, tree_hash
from paranoid.utils.ignore import build_spec, is_ignored, load_patterns, sync_patterns_to_storage

logger = logging.getLogger(__name__)


def _walk_bottom_up(
    root_path: Path,
    project_root: Path,
    spec: PathSpec,
) -> list[tuple[Path, str, str | None]]:
    """
    Collect (path, type, content_or_none) in bottom-up order: files first, then dirs by depth descending.
    Respects ignore patterns. Paths are absolute.
    """
    root_path = root_path.resolve()
    project_root = project_root.resolve()
    files: list[tuple[Path, str, str | None]] = []
    dirs: list[tuple[Path, str, str | None]] = []

    if root_path.is_file():
        if is_ignored(root_path, project_root, spec):
            return []
        try:
            content = root_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        files.append((root_path, "file", content))
        return files

    if not root_path.is_dir():
        return []

    def recurse(current: Path) -> None:
        try:
            entries = list(current.iterdir())
        except OSError:
            return
        for entry in sorted(entries, key=lambda p: p.name):
            if entry.is_file():
                if is_ignored(entry, project_root, spec):
                    continue
                try:
                    content = entry.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                files.append((entry, "file", content))
            else:
                if is_ignored(entry, project_root, spec):
                    continue
                recurse(entry)
                dirs.append((entry, "directory", None))
        return

    recurse(root_path)
    if not is_ignored(root_path, project_root, spec):
        dirs.append((root_path, "directory", None))

    # Sort dirs by depth descending (deepest first)
    def depth(p: Path) -> int:
        try:
            return len(p.relative_to(project_root).parts)
        except ValueError:
            return 0

    dirs.sort(key=lambda x: depth(x[0]), reverse=True)
    return files + dirs


def run(args) -> None:
    """Run the summarize command."""
    config = load_config(None)
    model = getattr(args, "model", None) or config.get("default_model")
    if not model:
        print("Error: --model is required (or set default_model in config).", file=sys.stderr)
        sys.exit(1)

    dry_run = getattr(args, "dry_run", False)
    force = getattr(args, "force", False)
    paths: list[Path] = getattr(args, "paths", [])

    for path in paths:
        path = path.resolve()
        project_root = require_project_root(path)

        config = load_config(project_root)
        patterns_with_source = load_patterns(project_root, config)
        patterns = [p for p, _ in patterns_with_source]
        spec = build_spec(patterns)

        storage = SQLiteStorage(project_root)
        storage._connect()
        for msg in storage.get_migration_messages():
            print(f"Note: {msg}", file=sys.stderr)
        sync_patterns_to_storage(patterns_with_source, storage)

        items = _walk_bottom_up(path, project_root, spec)
        total = len(items)
        if total == 0:
            logger.info("No items to process under %s", path)
            storage.close()
            continue

        now = datetime.now(timezone.utc).isoformat()
        summarized = 0
        skipped = 0

        for i, (path_abs, item_type, content) in enumerate(items):
            path_str = path_abs.as_posix()
            progress = f"[{i + 1}/{total}]"
            if not dry_run:
                print(f"  {progress} processing: {path_str}", file=sys.stderr)
            try:
                if item_type == "file":
                    current_hash = content_hash(path_abs)
                    if not force and not needs_summarization(path_str, current_hash, storage):
                        if dry_run:
                            print(f"  {progress} would skip (unchanged): {path_str}", file=sys.stderr)
                        skipped += 1
                        continue
                    if dry_run:
                        print(f"  {progress} would summarize: {path_str}", file=sys.stderr)
                        summarized += 1
                        continue
                    existing = storage.get_summary(path_str)
                    existing_desc = existing.description if existing else None
                    language = detect_language(path_str)
                    try:
                        summary_text, model_version = llm_summarize_file(
                            path_str,
                            content or "",
                            model,
                            existing_summary=existing_desc,
                            language=language,
                        )
                    except OllamaConnectionError as e:
                        print(f"Error: Ollama unreachable: {e}", file=sys.stderr)
                        storage.close()
                        sys.exit(1)
                    except ContextOverflowException as e:
                        summary_text = f"Summary not available: {e}"
                        model_version = None
                        error_msg = str(e)
                    else:
                        error_msg = None
                    # Preserve original generated_at when re-summarizing; always set updated_at to now
                    generated_at = existing.generated_at if existing else now
                    summary = Summary(
                        path=path_str,
                        type="file",
                        hash=current_hash,
                        description=summary_text,
                        file_extension=path_abs.suffix or None,
                        language=language,
                        error=error_msg,
                        needs_update=False,
                        model=model,
                        model_version=model_version,
                        prompt_version=PROMPT_VERSION,
                        context_level=0,
                        generated_at=generated_at,
                        updated_at=now,
                    )
                    storage.set_summary(summary)
                    summarized += 1
                    logger.debug("%s summarized: %s", progress, path_str)
                else:
                    current_hash = tree_hash(path_str, storage)
                    if not force and not needs_summarization(path_str, current_hash, storage):
                        if dry_run:
                            print(f"  {progress} would skip (unchanged): {path_str}", file=sys.stderr)
                        skipped += 1
                        continue
                    if dry_run:
                        print(f"  {progress} would summarize: {path_str}", file=sys.stderr)
                        summarized += 1
                        continue
                    children = storage.list_children(path_str)
                    children_text = "\n".join(
                        f"  • {c.path}: {c.description}" for c in children
                    )
                    existing = storage.get_summary(path_str)
                    existing_desc = existing.description if existing else None
                    is_root = path_abs == project_root
                    primary_language = detect_directory_language(children)
                    try:
                        summary_text, model_version = llm_summarize_directory(
                            path_str,
                            children_text,
                            model,
                            existing_summary=existing_desc,
                            is_root=is_root,
                            primary_language=primary_language,
                        )
                    except OllamaConnectionError as e:
                        print(f"Error: Ollama unreachable: {e}", file=sys.stderr)
                        storage.close()
                        sys.exit(1)
                    except ContextOverflowException as e:
                        summary_text = f"Summary not available: {e}"
                        model_version = None
                        error_msg = str(e)
                    else:
                        error_msg = None
                    # Preserve original generated_at when re-summarizing; always set updated_at to now
                    generated_at = existing.generated_at if existing else now
                    summary = Summary(
                        path=path_str,
                        type="directory",
                        hash=current_hash,
                        description=summary_text,
                        file_extension=None,
                        language=primary_language,
                        error=error_msg,
                        needs_update=False,
                        model=model,
                        model_version=model_version,
                        prompt_version=PROMPT_VERSION,
                        context_level=0,
                        generated_at=generated_at,
                        updated_at=now,
                    )
                    storage.set_summary(summary)
                    summarized += 1
                    logger.debug("%s summarized: %s", progress, path_str)
            except Exception as e:
                logger.exception("Failed to process %s: %s", path_str, e)
                print(f"  {progress} error: {path_str} — {e}", file=sys.stderr)

        storage.close()
        if not dry_run:
            print(f"Done: {summarized} summarized, {skipped} skipped (unchanged).", file=sys.stderr)
        else:
            print(f"Dry run: would summarize {summarized}, would skip {skipped}.", file=sys.stderr)
