"""SQLite implementation of the Storage interface."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from paranoid import config as paranoid_config
from paranoid.storage.base import StorageBase
from paranoid.storage.migrations import SCHEMA_VERSION_CURRENT, run_migrations
from paranoid.storage.models import IgnorePattern, ProjectStats, Summary

# Phase 5B graph types (analysis does not import storage, so no cycle)
from paranoid.analysis.entities import CodeEntity, EntityType
from paranoid.analysis.relationships import Relationship, RelationshipType


def _normalize_path(path: Path | str) -> str:
    """Return absolute, normalized path as posix string for storage."""
    p = Path(path).resolve()
    return p.as_posix()


class SQLiteStorage(StorageBase):
    """Storage backend using SQLite in project_root/.paranoid-coder/summaries.db."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = Path(project_root).resolve()
        self._db_dir = self._project_root / paranoid_config.PARANOID_DIR
        self._db_path = self._db_dir / paranoid_config.SUMMARIES_DB
        self._conn: sqlite3.Connection | None = None
        self._migration_messages: list[str] = []

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        self._db_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()
        return self._conn

    def _ensure_schema(self) -> None:
        conn = self._conn
        if conn is None:
            return
        self._migration_messages = run_migrations(conn)
        # Set initial metadata if missing (new DB)
        cur = conn.execute("SELECT value FROM metadata WHERE key = ?", ("project_root",))
        if cur.fetchone() is None:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?), (?, ?), (?, ?), (?, ?)",
                (
                    "project_root",
                    self._project_root.as_posix(),
                    "created_at",
                    now,
                    "version",
                    "1",
                    "schema_version",
                    SCHEMA_VERSION_CURRENT,
                ),
            )
            conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def get_migration_messages(self) -> list[str]:
        """Return and clear any migration notices from the last connect (show once per session)."""
        messages = self._migration_messages
        self._migration_messages = []
        return messages

    def __enter__(self) -> SQLiteStorage:
        self._connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_summary(self, path: Path | str) -> Summary | None:
        key = _normalize_path(path)
        conn = self._connect()
        row = conn.execute(
            "SELECT path, type, hash, description, file_extension, language, error, needs_update, "
            "model, model_version, prompt_version, context_level, generated_at, updated_at, "
            "tokens_used, generation_time_ms FROM summaries WHERE path = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return _row_to_summary(row)

    def set_summary(self, summary: Summary) -> None:
        key = _normalize_path(summary.path)
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO summaries (
                path, type, hash, description, file_extension, language, error, needs_update,
                model, model_version, prompt_version, context_level, generated_at, updated_at,
                tokens_used, generation_time_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                type=excluded.type, hash=excluded.hash, description=excluded.description,
                file_extension=excluded.file_extension, language=excluded.language, error=excluded.error,
                needs_update=excluded.needs_update, model=excluded.model, model_version=excluded.model_version,
                prompt_version=excluded.prompt_version, context_level=excluded.context_level,
                generated_at=excluded.generated_at, updated_at=excluded.updated_at,
                tokens_used=excluded.tokens_used, generation_time_ms=excluded.generation_time_ms
            """,
            (
                key,
                summary.type,
                summary.hash,
                summary.description,
                summary.file_extension,
                summary.language,
                summary.error,
                1 if summary.needs_update else 0,
                summary.model,
                summary.model_version,
                summary.prompt_version,
                summary.context_level,
                summary.generated_at,
                summary.updated_at,
                summary.tokens_used,
                summary.generation_time_ms,
            ),
        )
        conn.commit()

    def delete_summary(self, path: Path | str) -> None:
        key = _normalize_path(path)
        conn = self._connect()
        conn.execute("DELETE FROM summaries WHERE path = ?", (key,))
        conn.commit()

    def list_children(self, path: Path | str) -> list[Summary]:
        parent = _normalize_path(path)
        if not parent.endswith("/"):
            parent = parent + "/"
        # Direct children: path starts with parent and has no slash after the first segment
        # Exclude paths matching prefix + "%/%" (e.g. base/subdir/nested.py)
        prefix = parent
        prefix_with_subpath = parent + "%/%"
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT path, type, hash, description, file_extension, language, error, needs_update,
                   model, model_version, prompt_version, context_level, generated_at, updated_at,
                   tokens_used, generation_time_ms
            FROM summaries
            WHERE path LIKE ? AND path NOT LIKE ?
            ORDER BY path
            """,
            (prefix + "%", prefix_with_subpath),
        ).fetchall()
        return [_row_to_summary(row) for row in rows]

    def get_metadata(self, key: str) -> str | None:
        conn = self._connect()
        row = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return row["value"] if row is not None else None

    def set_metadata(self, key: str, value: str) -> None:
        conn = self._connect()
        conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

    def add_ignore_pattern(self, pattern: str, source: str) -> None:
        conn = self._connect()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO ignore_patterns (pattern, added_at, source) VALUES (?, ?, ?)",
            (pattern, now, source),
        )
        conn.commit()

    def set_ignore_patterns_for_source(self, source: str, patterns: list[str]) -> None:
        conn = self._connect()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("DELETE FROM ignore_patterns WHERE source = ?", (source,))
        for pattern in patterns:
            conn.execute(
                "INSERT INTO ignore_patterns (pattern, added_at, source) VALUES (?, ?, ?)",
                (pattern, now, source),
            )
        conn.commit()

    def get_ignore_patterns(self) -> list[IgnorePattern]:
        conn = self._connect()
        rows = conn.execute(
            "SELECT id, pattern, added_at, source FROM ignore_patterns ORDER BY id"
        ).fetchall()
        return [
            IgnorePattern(
                id=row["id"],
                pattern=row["pattern"],
                added_at=row["added_at"],
                source=row["source"],
            )
            for row in rows
        ]

    def get_stats(self, scope_path: str | None = None) -> ProjectStats:
        conn = self._connect()
        prefix = _normalize_path(scope_path) if scope_path else None
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"

        if prefix is None:
            count_rows = conn.execute(
                "SELECT type, COUNT(*) AS cnt FROM summaries GROUP BY type"
            ).fetchall()
            last_row = conn.execute("SELECT MAX(updated_at) AS m FROM summaries").fetchone()
            model_rows = conn.execute(
                "SELECT model, COUNT(*) AS cnt FROM summaries GROUP BY model ORDER BY cnt DESC"
            ).fetchall()
            language_rows = conn.execute(
                "SELECT COALESCE(language, 'unknown') AS lang, COUNT(*) AS cnt "
                "FROM summaries WHERE type = 'file' GROUP BY lang ORDER BY cnt DESC"
            ).fetchall()
        else:
            # Scope to paths equal to scope_path (no trailing slash) or under it
            scope_base = prefix.rstrip("/")
            count_rows = conn.execute(
                "SELECT type, COUNT(*) AS cnt FROM summaries WHERE path = ? OR path LIKE ? GROUP BY type",
                (scope_base, prefix + "%"),
            ).fetchall()
            last_row = conn.execute(
                "SELECT MAX(updated_at) AS m FROM summaries WHERE path = ? OR path LIKE ?",
                (scope_base, prefix + "%"),
            ).fetchone()
            model_rows = conn.execute(
                "SELECT model, COUNT(*) AS cnt FROM summaries WHERE path = ? OR path LIKE ? GROUP BY model ORDER BY cnt DESC",
                (scope_base, prefix + "%"),
            ).fetchall()
            language_rows = conn.execute(
                "SELECT COALESCE(language, 'unknown') AS lang, COUNT(*) AS cnt "
                "FROM summaries WHERE type = 'file' AND (path = ? OR path LIKE ?) GROUP BY lang ORDER BY cnt DESC",
                (scope_base, prefix + "%"),
            ).fetchall()

        count_by_type: dict[str, int] = {row["type"]: row["cnt"] for row in count_rows}
        last_updated_at: str | None = last_row["m"] if last_row and last_row["m"] else None
        model_breakdown = [(row["model"], row["cnt"]) for row in model_rows]
        language_breakdown = [(row["lang"], row["cnt"]) for row in language_rows]
        return ProjectStats(
            count_by_type=count_by_type,
            last_updated_at=last_updated_at,
            model_breakdown=model_breakdown,
            language_breakdown=language_breakdown,
        )

    def get_all_summaries(self, scope_path: str | None = None) -> list[Summary]:
        conn = self._connect()
        prefix = _normalize_path(scope_path) if scope_path else None
        if prefix and not prefix.endswith("/"):
            prefix = prefix + "/"

        if prefix is None:
            rows = conn.execute(
                "SELECT path, type, hash, description, file_extension, language, error, needs_update, "
                "model, model_version, prompt_version, context_level, generated_at, updated_at, "
                "tokens_used, generation_time_ms FROM summaries ORDER BY path"
            ).fetchall()
        else:
            scope_base = prefix.rstrip("/")
            rows = conn.execute(
                "SELECT path, type, hash, description, file_extension, language, error, needs_update, "
                "model, model_version, prompt_version, context_level, generated_at, updated_at, "
                "tokens_used, generation_time_ms FROM summaries "
                "WHERE path = ? OR path LIKE ? ORDER BY path",
                (scope_base, prefix + "%"),
            ).fetchall()
        return [_row_to_summary(row) for row in rows]

    # --- Phase 5B: code graph ---

    def store_entity(self, entity: CodeEntity) -> int:
        """Insert a code entity; return its id."""
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO code_entities (
                file_path, type, name, qualified_name, parent_name,
                lineno, end_lineno, docstring, signature, language,
                parent_entity_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity.file_path,
                entity.type.value,
                entity.name,
                entity.qualified_name,
                entity.parent_name,
                entity.lineno,
                entity.end_lineno,
                entity.docstring,
                entity.signature,
                entity.language,
                entity.parent_entity_id,
            ),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def store_relationship(self, rel: Relationship) -> int:
        """Insert a code relationship; return its id."""
        conn = self._connect()
        conn.execute(
            """
            INSERT INTO code_relationships (
                from_entity_id, to_entity_id, from_file, to_file,
                relationship_type, location
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rel.from_entity_id,
                rel.to_entity_id,
                rel.from_file,
                rel.to_file,
                rel.relationship_type.value,
                rel.location,
            ),
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_entities_by_file(self, file_path: str) -> list[CodeEntity]:
        """Return all entities for the given file (normalized path)."""
        key = _normalize_path(file_path)
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT id, file_path, type, name, qualified_name, parent_name,
                   lineno, end_lineno, docstring, signature, language,
                   parent_entity_id
            FROM code_entities
            WHERE file_path = ?
            ORDER BY lineno
            """,
            (key,),
        ).fetchall()
        return [_row_to_entity(row) for row in rows]

    def get_entity_by_qualified_name(
        self, qualified_name: str, scope_file: str | None = None
    ) -> CodeEntity | None:
        """
        Find an entity by qualified name (e.g. "User.login", "greet").
        If scope_file is given, prefer entities from that file first.
        """
        conn = self._connect()
        # Exact match first
        row = conn.execute(
            """
            SELECT id, file_path, type, name, qualified_name, parent_name,
                   lineno, end_lineno, docstring, signature, language,
                   parent_entity_id
            FROM code_entities
            WHERE qualified_name = ?
            ORDER BY CASE WHEN file_path = ? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (qualified_name, scope_file or ""),
        ).fetchone()
        if row is not None:
            return _row_to_entity(row)
        # Fallback: simple name match (e.g. "greet" when no qualified name)
        row = conn.execute(
            """
            SELECT id, file_path, type, name, qualified_name, parent_name,
                   lineno, end_lineno, docstring, signature, language,
                   parent_entity_id
            FROM code_entities
            WHERE name = ?
            ORDER BY CASE WHEN file_path = ? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (qualified_name, scope_file or ""),
        ).fetchone()
        if row is not None:
            return _row_to_entity(row)
        return None

    def delete_entities_for_file(self, file_path: str) -> None:
        """Remove all entities and their relationships for the given file."""
        key = _normalize_path(file_path)
        conn = self._connect()
        conn.execute("DELETE FROM code_relationships WHERE from_file = ? OR to_file = ?", (key, key))
        conn.execute("DELETE FROM code_entities WHERE file_path = ?", (key,))
        conn.commit()

    def get_analysis_file_hash(self, file_path: str) -> str | None:
        """Return stored content hash for a file, or None if not analyzed."""
        key = _normalize_path(file_path)
        conn = self._connect()
        row = conn.execute(
            "SELECT content_hash FROM analysis_file_hashes WHERE file_path = ?",
            (key,),
        ).fetchone()
        return row["content_hash"] if row is not None else None

    def set_analysis_file_hash(self, file_path: str, content_hash: str) -> None:
        """Store content hash for a file after successful analysis."""
        key = _normalize_path(file_path)
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO analysis_file_hashes (file_path, content_hash) VALUES (?, ?)",
            (key, content_hash),
        )
        conn.commit()

    def get_imports_for_file(self, file_path: str) -> list[str]:
        """Return imported module names for the given file (from IMPORTS relationships)."""
        key = _normalize_path(file_path)
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT to_file FROM code_relationships
            WHERE from_file = ? AND relationship_type = 'imports' AND to_file IS NOT NULL
            ORDER BY to_file
            """,
            (key,),
        ).fetchall()
        return [row["to_file"] for row in rows]

    def get_callers_of_entity(self, entity_id: int) -> list[tuple[str, str, str | None]]:
        """
        Return (caller_qualified_name, caller_file, location) for entities that call this one.
        """
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT e.qualified_name, e.file_path, r.location
            FROM code_relationships r
            JOIN code_entities e ON e.id = r.from_entity_id
            WHERE r.to_entity_id = ? AND r.relationship_type = 'calls'
            ORDER BY e.file_path, e.qualified_name
            """,
            (entity_id,),
        ).fetchall()
        return [(row["qualified_name"], row["file_path"], row["location"]) for row in rows]

    def get_callees_of_entity(self, entity_id: int) -> list[tuple[str, str | None, str | None]]:
        """
        Return (callee_qualified_name_or_target, callee_file, location) for what this entity calls.
        Uses to_entity.qualified_name when resolved, else to_file as target name.
        """
        conn = self._connect()
        rows = conn.execute(
            """
            SELECT COALESCE(e.qualified_name, r.to_file) AS target, e.file_path, r.location
            FROM code_relationships r
            LEFT JOIN code_entities e ON e.id = r.to_entity_id
            WHERE r.from_entity_id = ? AND r.relationship_type = 'calls'
            ORDER BY target
            """,
            (entity_id,),
        ).fetchall()
        return [
            (row["target"] or "(unknown)", row["file_path"], row["location"])
            for row in rows
        ]

    def get_summary_context(
        self, summary_path: str
    ) -> tuple[str, int, int, str] | None:
        """
        Return (imports_hash, callers_count, callees_count, context_version) for a summary.
        None if not stored.
        """
        key = _normalize_path(summary_path)
        conn = self._connect()
        row = conn.execute(
            """
            SELECT imports_hash, callers_count, callees_count, context_version
            FROM summary_context WHERE summary_path = ?
            """,
            (key,),
        ).fetchone()
        if row is None:
            return None
        return (
            row["imports_hash"] or "",
            row["callers_count"] or 0,
            row["callees_count"] or 0,
            row["context_version"] or "",
        )

    def set_summary_context(
        self,
        summary_path: str,
        imports_hash: str,
        callers_count: int,
        callees_count: int,
        context_version: str = "1",
    ) -> None:
        """Store context snapshot for a summary (used for smart invalidation)."""
        key = _normalize_path(summary_path)
        conn = self._connect()
        conn.execute(
            """
            INSERT OR REPLACE INTO summary_context
            (summary_path, imports_hash, callers_count, callees_count, context_version)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, imports_hash, callers_count, callees_count, context_version),
        )
        conn.commit()


def _row_to_entity(row: sqlite3.Row) -> CodeEntity:
    return CodeEntity(
        file_path=row["file_path"],
        type=EntityType(row["type"]),
        name=row["name"],
        qualified_name=row["qualified_name"],
        parent_name=row["parent_name"],
        lineno=row["lineno"] or 0,
        end_lineno=row["end_lineno"] or 0,
        docstring=row["docstring"],
        signature=row["signature"],
        language=row["language"] or "python",
        id=row["id"],
        parent_entity_id=row["parent_entity_id"],
    )


def _row_to_summary(row: sqlite3.Row) -> Summary:
    return Summary(
        path=row["path"],
        type=row["type"],
        hash=row["hash"],
        description=row["description"],
        file_extension=row["file_extension"],
        language=row["language"] if "language" in row.keys() else None,
        error=row["error"],
        needs_update=bool(row["needs_update"]),
        model=row["model"] or "",
        model_version=row["model_version"],
        prompt_version=row["prompt_version"] or "",
        context_level=row["context_level"] or 0,
        generated_at=row["generated_at"] or "",
        updated_at=row["updated_at"] or "",
        tokens_used=row["tokens_used"],
        generation_time_ms=row["generation_time_ms"],
    )
