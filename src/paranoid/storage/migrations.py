"""Database schema migrations for summaries.db.

Schema versions:
  1 = original
  2 = language column (Phase 4 multi-language)
  3 = graph tables (Phase 5B: code_entities, code_relationships, summary_context, doc_quality)
  4 = analysis_file_hashes (incremental analyze)
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION_CURRENT = "4"

# Primary schema (summaries, ignore_patterns, metadata)
SCHEMA_SQL = """
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

# Phase 5B: code graph (no FK from code_entities.file_path so analyze can run without summaries)
SCHEMA_V3_SQL = """
CREATE TABLE IF NOT EXISTS code_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    parent_name TEXT,
    lineno INTEGER,
    end_lineno INTEGER,
    docstring TEXT,
    signature TEXT,
    language TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    parent_entity_id INTEGER,
    FOREIGN KEY (parent_entity_id) REFERENCES code_entities(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_entities_name ON code_entities(name);
CREATE INDEX IF NOT EXISTS idx_entities_qualified_name ON code_entities(qualified_name);
CREATE INDEX IF NOT EXISTS idx_entities_type ON code_entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_file ON code_entities(file_path);

CREATE TABLE IF NOT EXISTS code_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity_id INTEGER,
    to_entity_id INTEGER,
    from_file TEXT,
    to_file TEXT,
    relationship_type TEXT NOT NULL,
    location TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (from_entity_id) REFERENCES code_entities(id) ON DELETE CASCADE,
    FOREIGN KEY (to_entity_id) REFERENCES code_entities(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_rel_from ON code_relationships(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_rel_to ON code_relationships(to_entity_id);
CREATE INDEX IF NOT EXISTS idx_rel_type ON code_relationships(relationship_type);

CREATE TABLE IF NOT EXISTS summary_context (
    summary_path TEXT PRIMARY KEY,
    imports_hash TEXT,
    callers_count INTEGER DEFAULT 0,
    callees_count INTEGER DEFAULT 0,
    context_version TEXT
);

CREATE TABLE IF NOT EXISTS doc_quality (
    entity_id INTEGER PRIMARY KEY,
    has_docstring INTEGER DEFAULT 0,
    has_examples INTEGER DEFAULT 0,
    has_type_hints INTEGER DEFAULT 0,
    priority_score INTEGER DEFAULT 0,
    last_reviewed TEXT,
    FOREIGN KEY (entity_id) REFERENCES code_entities(id) ON DELETE CASCADE
);
"""

# Schema v4: incremental analyze (content hash per file)
SCHEMA_V4_SQL = """
CREATE TABLE IF NOT EXISTS analysis_file_hashes (
    file_path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL
);
"""


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
        conn.execute(
            "UPDATE summaries SET language = 'python' WHERE type = 'file' AND (language IS NULL OR language = '')"
        )
        conn.commit()
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("schema_version", "2"),
        )
        conn.commit()
        messages.append(
            "Database migrated to schema v2: added language support. "
            "Existing file summaries marked as Python."
        )
    return messages


def _migrate_to_v3(conn: sqlite3.Connection) -> list[str]:
    """
    Add Phase 5B graph tables: code_entities, code_relationships, summary_context, doc_quality.
    No FK from code_entities.file_path to summaries so that `paranoid analyze` can run standalone.
    """
    messages: list[str] = []
    conn.executescript(SCHEMA_V3_SQL)
    conn.commit()
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("schema_version", "3"),
    )
    conn.commit()
    messages.append("Database migrated to schema v3: added code graph tables (Phase 5B).")
    return messages


def _migrate_to_v4(conn: sqlite3.Connection) -> list[str]:
    """
    Add analysis_file_hashes table for incremental analyze (content hash vs stored hash).
    """
    messages: list[str] = []
    conn.executescript(SCHEMA_V4_SQL)
    conn.commit()
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        ("schema_version", "4"),
    )
    conn.commit()
    messages.append(
        "Database migrated to schema v4: added analysis file hashes for incremental analyze."
    )
    return messages


def _migrate_context_level(conn: sqlite3.Connection) -> list[str]:
    """
    Ensure context_level column exists and backfill NULL to 0.
    Handles DBs created before context_level was added; existing summaries default to 0.
    """
    messages: list[str] = []
    cur = conn.execute("PRAGMA table_info(summaries)")
    columns = [row[1] for row in cur.fetchall()]
    if "context_level" not in columns:
        conn.execute("ALTER TABLE summaries ADD COLUMN context_level INTEGER DEFAULT 0")
        conn.commit()
        messages.append(
            "Database migrated: added context_level column. Existing summaries marked as 0 (isolated)."
        )
    # Backfill any NULL to 0 (e.g. from older inserts)
    conn.execute("UPDATE summaries SET context_level = 0 WHERE context_level IS NULL")
    conn.commit()
    return messages


def run_migrations(conn: sqlite3.Connection) -> list[str]:
    """
    Ensure schema is up to date. Run base schema, then migrations in order.
    Returns list of user-facing migration messages.
    """
    messages: list[str] = []
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    messages.extend(_migrate_language_column(conn))
    messages.extend(_migrate_context_level(conn))

    cur = conn.execute("SELECT value FROM metadata WHERE key = ?", ("schema_version",))
    row = cur.fetchone()
    current_version = int(row["value"]) if row and row["value"] else 0

    if current_version < 3:
        messages.extend(_migrate_to_v3(conn))
    if current_version < 4:
        messages.extend(_migrate_to_v4(conn))

    return messages
