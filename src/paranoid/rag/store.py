"""Vector store for summary embeddings using sqlite-vec vec0 in the project's summaries.db."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from paranoid import config as paranoid_config

try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None  # type: ignore[assignment]

VEC_TABLE = "vec_summaries"
METADATA_EMBED_DIM = "rag_embedding_dim"
METADATA_VEC_SCHEMA_VERSION = "rag_vec_schema_version"
VEC_SCHEMA_VERSION = "2"  # path, type, updated_at as metadata for sync and filter


@dataclass
class VecResult:
    """A single result from vector similarity search."""

    path: str
    type: str  # "file" or "directory"
    description: str
    distance: float


def _db_path(project_root: Path) -> Path:
    """Path to summaries.db for the project."""
    root = Path(project_root).resolve()
    return root / paranoid_config.PARANOID_DIR / paranoid_config.SUMMARIES_DB


def _load_extension(conn: sqlite3.Connection) -> None:
    """Load sqlite_vec extension. Raises if sqlite_vec not installed or load fails."""
    if sqlite_vec is None:
        raise ImportError(
            "RAG requires the sqlite-vec package. Install with: pip install sqlite-vec"
        )
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def _get_stored_embed_dim(conn: sqlite3.Connection) -> int | None:
    """Return stored embedding dimension from metadata, or None."""
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = ?", (METADATA_EMBED_DIM,)
    ).fetchone()
    if row is None:
        return None
    try:
        return int(row[0])
    except (TypeError, ValueError):
        return None


def _set_stored_embed_dim(conn: sqlite3.Connection, dim: int) -> None:
    """Store embedding dimension in metadata."""
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        (METADATA_EMBED_DIM, str(dim)),
    )
    conn.commit()


def _get_vec_schema_version(conn: sqlite3.Connection) -> str | None:
    """Return stored vec schema version, or None."""
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = ?", (METADATA_VEC_SCHEMA_VERSION,)
    ).fetchone()
    return row[0] if row is not None else None


def _set_vec_schema_version(conn: sqlite3.Connection, version: str) -> None:
    """Store vec schema version in metadata."""
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
        (METADATA_VEC_SCHEMA_VERSION, version),
    )
    conn.commit()


def _vec_table_exists(conn: sqlite3.Connection) -> bool:
    """Return True if vec_summaries virtual table exists."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (VEC_TABLE,),
    ).fetchone()
    return row is not None


class VectorStore:
    """
    Vector store for summary embeddings in the project's summaries.db.
    Uses sqlite-vec vec0 virtual table. Open with context manager or call close().
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = Path(project_root).resolve()
        self._db_path = _db_path(self._project_root)
        self._conn: sqlite3.Connection | None = None
        self._embed_dim: int | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        if not self._db_path.parent.is_dir():
            raise FileNotFoundError(
                f"Project storage not found: {self._db_path.parent}. Run 'paranoid init' first."
            )
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        _load_extension(self._conn)
        self._embed_dim = _get_stored_embed_dim(self._conn)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> VectorStore:
        self._connect()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def ensure_table(self, dim: int) -> None:
        """
        Ensure vec_summaries table exists with the given embedding dimension.
        If table exists with a different dim or old schema version, it is dropped and recreated.
        Schema: path, type, updated_at as metadata (for sync and filter); +description auxiliary.
        """
        conn = self._connect()
        if _vec_table_exists(conn):
            stored_dim = _get_stored_embed_dim(conn)
            schema_ver = _get_vec_schema_version(conn)
            if stored_dim == dim and schema_ver == VEC_SCHEMA_VERSION:
                return
            conn.execute(f"DROP TABLE IF EXISTS {VEC_TABLE}")
            conn.commit()
        # vec0: embedding, metadata (path, type, updated_at for sync/filter), auxiliary +description
        conn.execute(
            f"""
            CREATE VIRTUAL TABLE {VEC_TABLE} USING vec0(
                embedding FLOAT[{dim}],
                path TEXT,
                type TEXT,
                updated_at TEXT,
                +description TEXT
            )
            """
        )
        conn.commit()
        _set_stored_embed_dim(conn, dim)
        _set_vec_schema_version(conn, VEC_SCHEMA_VERSION)
        self._embed_dim = dim

    def embed_dim(self) -> int | None:
        """Return the current embedding dimension (from metadata), or None if not yet set."""
        self._connect()
        return self._embed_dim

    def count(self) -> int:
        """Return number of rows in the vector table. Returns 0 if table does not exist."""
        conn = self._connect()
        if not _vec_table_exists(conn):
            return 0
        row = conn.execute(f"SELECT COUNT(*) FROM {VEC_TABLE}").fetchone()
        return row[0] if row else 0

    def insert(
        self,
        path: str,
        type_: str,
        updated_at: str,
        description: str,
        embedding: list[float],
    ) -> None:
        """Insert one (path, type, updated_at, description, embedding) into the vector table."""
        conn = self._connect()
        dim = len(embedding)
        self.ensure_table(dim)
        if sqlite_vec is None:
            raise ImportError("sqlite-vec is required for vector insert")
        blob = sqlite_vec.serialize_float32(embedding)
        conn.execute(
            f"INSERT INTO {VEC_TABLE} (embedding, path, type, updated_at, description) VALUES (?, ?, ?, ?, ?)",
            (blob, path, type_, updated_at, description),
        )
        conn.commit()

    def insert_batch(
        self,
        rows: list[tuple[str, str, str, str, list[float]]],
    ) -> None:
        """Insert multiple (path, type, updated_at, description, embedding) rows."""
        if not rows:
            return
        conn = self._connect()
        dim = len(rows[0][4])
        self.ensure_table(dim)
        if sqlite_vec is None:
            raise ImportError("sqlite-vec is required for vector insert")
        for path, type_, updated_at, description, embedding in rows:
            blob = sqlite_vec.serialize_float32(embedding)
            conn.execute(
                f"INSERT INTO {VEC_TABLE} (embedding, path, type, updated_at, description) VALUES (?, ?, ?, ?, ?)",
                (blob, path, type_, updated_at, description),
            )
        conn.commit()

    def get_indexed_paths(self) -> dict[str, str]:
        """
        Return path -> updated_at for all rows in the vector table.
        Used for incremental sync: embed only new or changed summaries.
        Returns {} if table has old schema (no updated_at column).
        """
        conn = self._connect()
        if not _vec_table_exists(conn):
            return {}
        try:
            rows = conn.execute(
                f"SELECT path, updated_at FROM {VEC_TABLE}"
            ).fetchall()
            return {row["path"]: row["updated_at"] for row in rows}
        except sqlite3.OperationalError:
            # Old schema (e.g. no updated_at column) -> treat as empty so full reindex runs
            return {}

    def delete_by_path(self, path: str) -> None:
        """Remove the row(s) for the given path. No-op if not present."""
        conn = self._connect()
        if not _vec_table_exists(conn):
            return
        conn.execute(f"DELETE FROM {VEC_TABLE} WHERE path = ?", (path,))
        conn.commit()

    def clear(self) -> None:
        """Remove all rows from the vector table. Table and dimension are left as-is."""
        conn = self._connect()
        if not _vec_table_exists(conn):
            return
        conn.execute(f"DELETE FROM {VEC_TABLE}")
        conn.commit()

    def query_similar(
        self,
        query_embedding: list[float],
        vector_k: int = 20,
        type_filter: str | None = None,
        top_k: int | None = None,
    ) -> list[VecResult]:
        """
        Run KNN search. Fetches vector_k candidates, optionally filters by type, returns top_k.

        - vector_k: number of nearest neighbors to fetch from the index.
        - type_filter: "file" or "directory" to restrict results; None = both.
        - top_k: max results to return after filtering (default: vector_k).
        """
        conn = self._connect()
        if not _vec_table_exists(conn):
            return []
        stored_dim = _get_stored_embed_dim(conn)
        if stored_dim is None or len(query_embedding) != stored_dim:
            return []
        if sqlite_vec is None:
            raise ImportError("sqlite-vec is required for vector query")
        blob = sqlite_vec.serialize_float32(query_embedding)
        # Fetch more when filtering so we have enough after type filter
        k_fetch = vector_k * 2 if type_filter else vector_k
        try:
            rows = conn.execute(
                f"""
                SELECT path, type, description, distance
                FROM {VEC_TABLE}
                WHERE embedding MATCH ? AND k = ?
                """,
                (blob, k_fetch),
            ).fetchall()
            results = [
                VecResult(
                    path=row["path"],
                    type=row["type"] or "file",
                    description=row["description"],
                    distance=row["distance"],
                )
                for row in rows
            ]
        except sqlite3.OperationalError:
            # Old schema (no type column): fall back to path, description, distance
            rows = conn.execute(
                f"""
                SELECT path, description, distance
                FROM {VEC_TABLE}
                WHERE embedding MATCH ? AND k = ?
                """,
                (blob, k_fetch),
            ).fetchall()
            results = [
                VecResult(path=row["path"], type="file", description=row["description"], distance=row["distance"])
                for row in rows
            ]
        if type_filter:
            results = [r for r in results if r.type == type_filter]
        return results[: top_k if top_k is not None else vector_k]
