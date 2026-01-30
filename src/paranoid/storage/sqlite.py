"""SQLite implementation of the Storage interface."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from paranoid import config as paranoid_config
from paranoid.storage.base import StorageBase
from paranoid.storage.models import IgnorePattern, ProjectStats, Summary


def _normalize_path(path: Path | str) -> str:
    """Return absolute, normalized path as posix string for storage."""
    p = Path(path).resolve()
    return p.as_posix()


# Schema version in metadata: 1 = original, 2 = language column + backfill
SCHEMA_VERSION_CURRENT = "2"


def _migrate_language_column(conn: sqlite3.Connection) -> list[str]:
    """
    Add language column to summaries if missing (Phase 4 multi-language support).
    Backfill existing file rows as language='python'. Set metadata schema_version=2.
    Returns list of user-facing messages (e.g. migration notice); empty if no migration.
    """
    messages: list[str] = []
    cur = conn.execute("PRAGMA table_info(summaries)")
    columns = [row[1] for row in cur.fetchall()]
    if "language" not in columns:
        conn.execute("ALTER TABLE summaries ADD COLUMN language TEXT")
        conn.commit()
        # Backfill: prior to this we only supported Python
        conn.execute(
            "UPDATE summaries SET language = 'python' WHERE type = 'file' AND (language IS NULL OR language = '')"
        )
        conn.commit()
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION_CURRENT),
        )
        conn.commit()
        messages.append(
            "Database migrated to schema v2: added language support. "
            "Existing file summaries marked as Python."
        )
    return messages


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
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        self._migration_messages = _migrate_language_column(conn)
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


_SCHEMA_SQL = """
-- Primary summaries table
CREATE TABLE IF NOT EXISTS summaries (
    path TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    hash TEXT NOT NULL,
    description TEXT NOT NULL,
    file_extension TEXT,
    language TEXT,
    error TEXT,
    needs_update INTEGER DEFAULT 0,
    model TEXT NOT NULL,
    model_version TEXT,
    prompt_version TEXT NOT NULL,
    context_level INTEGER DEFAULT 0,
    generated_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    tokens_used INTEGER,
    generation_time_ms INTEGER
);
CREATE INDEX IF NOT EXISTS idx_type ON summaries(type);
CREATE INDEX IF NOT EXISTS idx_updated_at ON summaries(updated_at);
CREATE INDEX IF NOT EXISTS idx_needs_update ON summaries(needs_update);

-- Ignore patterns table
CREATE TABLE IF NOT EXISTS ignore_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    added_at TEXT NOT NULL,
    source TEXT
);
CREATE INDEX IF NOT EXISTS idx_ignore_source ON ignore_patterns(source);

-- Project metadata
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""
