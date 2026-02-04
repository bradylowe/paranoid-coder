"""Analyze command: extract code graph from project (Phase 5B)."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from paranoid.analysis import Parser
from paranoid.analysis.entities import CodeEntity, EntityType
from paranoid.analysis.relationships import Relationship, RelationshipType
from paranoid.config import load_config, require_project_root
from paranoid.llm.prompts import detect_language
from paranoid.storage import SQLiteStorage
from paranoid.utils.hashing import content_hash
from paranoid.utils.ignore import build_spec, is_ignored, load_patterns

# Bump when extraction logic or supported languages change
ANALYSIS_PARSER_VERSION = "1.0"


def _resolve_and_store_relationship(
    rel: Relationship,
    entity_id_map: dict[str, int],
    current_file: str,
    storage: SQLiteStorage,
) -> None:
    """
    Resolve from_entity_id and to_entity_id for entity-level relationships,
    then store the relationship.
    """
    # Resolve from_entity_id from caller/class qualified name
    if rel.from_entity_qualified_name and rel.from_entity_qualified_name in entity_id_map:
        rel.from_entity_id = entity_id_map[rel.from_entity_qualified_name]

    # Resolve to_entity_id for CALLS and INHERITS (target is in to_file)
    if rel.relationship_type in (RelationshipType.CALLS, RelationshipType.INHERITS):
        if rel.to_file:
            target = storage.get_entity_by_qualified_name(
                rel.to_file, scope_file=current_file
            )
            if target and target.id is not None:
                rel.to_entity_id = target.id

    storage.store_relationship(rel)


def _collect_files_to_analyze(
    path: Path,
    project_root: Path,
    spec,
    parser: Parser,
) -> list[Path]:
    """Collect analyzable files under path (respect ignore, supported languages)."""
    path = path.resolve()
    files: list[Path] = []

    if path.is_file():
        if is_ignored(path, project_root, spec):
            return []
        lang = detect_language(path)
        if parser.supports_language(lang):
            files.append(path)
        return files

    if not path.is_dir():
        return files

    for entry in path.rglob("*"):
        if not entry.is_file():
            continue
        if is_ignored(entry, project_root, spec):
            continue
        if not parser.supports_language(detect_language(entry)):
            continue
        files.append(entry)

    return sorted(files, key=lambda p: p.as_posix())


def run(args) -> None:
    """Run the analyze command."""
    path = getattr(args, "path", Path("."))
    path = Path(path).resolve()
    force = getattr(args, "force", False)
    verbose = getattr(args, "verbose", False)
    dry_run = getattr(args, "dry_run", False)

    project_root = require_project_root(path)

    config = load_config(project_root)
    patterns_with_source = load_patterns(project_root, config)
    patterns = [p for p, _ in patterns_with_source]
    spec = build_spec(patterns)

    storage = SQLiteStorage(project_root)
    storage._connect()
    for msg in storage.get_migration_messages():
        print(f"Note: {msg}", file=sys.stderr)

    parser = Parser()
    files = _collect_files_to_analyze(path, project_root, spec, parser)
    total = len(files)

    if total == 0:
        print(
            "No analyzable files found (Python, JavaScript, TypeScript).",
            file=sys.stderr,
        )
        return

    if dry_run:
        print(f"Would analyze {total} file(s).", file=sys.stderr)
        for f in files:
            print(f"  {f.as_posix()}", file=sys.stderr)
        return

    start = time.perf_counter()
    entities_stored = 0
    relationships_stored = 0
    skipped = 0
    errors = 0

    for i, file_path in enumerate(files):
        file_path_str = file_path.resolve().as_posix()

        # Skip unchanged files unless --force
        if not force:
            try:
                current_hash = content_hash(file_path)
                stored_hash = storage.get_analysis_file_hash(file_path_str)
                if stored_hash is not None and stored_hash == current_hash:
                    skipped += 1
                    if verbose:
                        print(f"  [{i + 1}/{total}] {file_path_str} (unchanged, skip)", file=sys.stderr)
                    continue
            except (ValueError, OSError):
                pass  # File missing or unreadable; will fail below

        if verbose:
            print(f"  [{i + 1}/{total}] {file_path_str}", file=sys.stderr)

        storage.delete_entities_for_file(file_path_str)

        try:
            language = detect_language(file_path_str)
            entities, relationships = parser.parse_file(file_path_str, language)
        except Exception as e:
            if verbose:
                print(f"    parse error: {e}", file=sys.stderr)
            errors += 1
            continue

        # Store entities and build qualified_name -> id map for this file
        entity_id_map: dict[str, int] = {}
        current_class_id: int | None = None
        for entity in entities:
            if entity.type == EntityType.CLASS:
                current_class_id = storage.store_entity(entity)
                entity.id = current_class_id
                entity_id_map[entity.qualified_name] = current_class_id
                entities_stored += 1
            elif entity.type == EntityType.METHOD and current_class_id is not None:
                entity.parent_entity_id = current_class_id
                eid = storage.store_entity(entity)
                entity.id = eid
                entity_id_map[entity.qualified_name] = eid
                entities_stored += 1
            else:
                entity.parent_entity_id = None
                eid = storage.store_entity(entity)
                entity.id = eid
                entity_id_map[entity.qualified_name] = eid
                entities_stored += 1
                if entity.type == EntityType.FUNCTION:
                    current_class_id = None

        # Resolve and store relationships (entity-level linking for calls/inheritance)
        for rel in relationships:
            _resolve_and_store_relationship(
                rel, entity_id_map, file_path_str, storage
            )
            relationships_stored += 1

        # Record content hash so we can skip this file next run if unchanged
        try:
            storage.set_analysis_file_hash(file_path_str, content_hash(file_path))
        except (ValueError, OSError):
            pass

    elapsed = time.perf_counter() - start

    # Store analysis metadata (timestamp, parser version)
    storage.set_metadata("analysis_timestamp", datetime.now(timezone.utc).isoformat())
    storage.set_metadata("analysis_parser_version", ANALYSIS_PARSER_VERSION)

    analyzed_count = total - skipped
    print(
        f"Analyzed {analyzed_count} file(s), skipped {skipped} unchanged, in {elapsed:.1f}s: "
        f"{entities_stored} entities, {relationships_stored} relationships.",
        file=sys.stderr,
    )
    if errors:
        print(f"  ({errors} file(s) had parse errors)", file=sys.stderr)
