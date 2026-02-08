"""Unit tests for RAG vector store (summaries and entity-level embeddings)."""

from __future__ import annotations

from pathlib import Path

import pytest

from paranoid.commands.init_cmd import run as init_run
from paranoid.rag.store import VecResult, VectorStore

pytest.importorskip("sqlite_vec")


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Project root with initialized .paranoid-coder (proper schema)."""
    init_run(type("Args", (), {"path": tmp_path})())
    return tmp_path


@pytest.fixture
def vec_store(project_root: Path) -> VectorStore:
    """VectorStore for temp project. Closed after test."""
    store = VectorStore(project_root)
    yield store
    store.close()


def test_ensure_entities_table_and_insert(vec_store: VectorStore) -> None:
    """Entity table can be created and entities inserted."""
    dim = 4
    vec_store._connect()
    vec_store.ensure_entities_table(dim)
    vec_store.insert_entity(
        entity_id=1,
        file_path="/project/src/auth.py",
        qualified_name="authenticate_user",
        lineno=5,
        end_lineno=8,
        updated_at="2026-01-01T00:00:00",
        description="authenticate_user\nValidate credentials",
        signature="(username: str, password: str) -> bool",
        embedding=[0.1] * dim,
    )
    assert vec_store.entity_count() == 1


def test_insert_entities_batch(vec_store: VectorStore) -> None:
    """Batch insert of entities works."""
    dim = 4
    rows = [
        (
            1,
            "/project/src/auth.py",
            "authenticate_user",
            5,
            8,
            "2026-01-01T00:00:00",
            "authenticate_user\nValidate credentials",
            "(username: str, password: str) -> bool",
            [0.1] * dim,
        ),
        (
            2,
            "/project/src/auth.py",
            "UserService.login",
            15,
            17,
            "2026-01-01T00:00:00",
            "UserService.login\nHandles user login",
            "(self, username: str) -> None",
            [0.2] * dim,
        ),
    ]
    vec_store._connect()
    vec_store.insert_entities_batch(rows)
    assert vec_store.entity_count() == 2


def test_query_similar_entities(vec_store: VectorStore) -> None:
    """query_similar_entities returns VecResult with entity fields."""
    dim = 4
    vec_store._connect()
    vec_store.ensure_entities_table(dim)
    vec_store.insert_entity(
        entity_id=1,
        file_path="/project/src/auth.py",
        qualified_name="authenticate_user",
        lineno=5,
        end_lineno=8,
        updated_at="2026-01-01T00:00:00",
        description="authenticate_user\nValidate credentials",
        signature="(username: str, password: str) -> bool",
        embedding=[0.1] * dim,
    )
    results = vec_store.query_similar_entities([0.1] * dim, vector_k=5, top_k=5)
    assert len(results) >= 1
    r = results[0]
    assert r.type == "entity"
    assert r.entity_id == 1
    assert r.path == "/project/src/auth.py"
    assert r.qualified_name == "authenticate_user"
    assert r.lineno == 5
    assert r.end_lineno == 8
    assert r.signature == "(username: str, password: str) -> bool"


def test_get_indexed_entities(vec_store: VectorStore) -> None:
    """get_indexed_entities returns entity_id -> updated_at."""
    dim = 4
    vec_store._connect()
    vec_store.ensure_entities_table(dim)
    vec_store.insert_entity(
        entity_id=42,
        file_path="/project/foo.py",
        qualified_name="bar",
        lineno=1,
        end_lineno=2,
        updated_at="2026-02-01T12:00:00",
        description="bar",
        signature=None,
        embedding=[0.0] * dim,
    )
    indexed = vec_store.get_indexed_entities()
    assert indexed == {42: "2026-02-01T12:00:00"}


def test_delete_entity_by_id(vec_store: VectorStore) -> None:
    """delete_entity_by_id removes the entity from vec_entities."""
    dim = 4
    vec_store._connect()
    vec_store.ensure_entities_table(dim)
    vec_store.insert_entity(
        entity_id=1,
        file_path="/project/x.py",
        qualified_name="f",
        lineno=1,
        end_lineno=2,
        updated_at="",
        description="f",
        signature=None,
        embedding=[0.0] * dim,
    )
    assert vec_store.entity_count() == 1
    vec_store.delete_entity_by_id(1)
    assert vec_store.entity_count() == 0


def test_clear_entities(vec_store: VectorStore) -> None:
    """clear_entities removes all entity rows."""
    dim = 4
    vec_store._connect()
    vec_store.insert_entities_batch(
        [
            (1, "/p/a.py", "a", 1, 2, "", "a", None, [0.0] * dim),
            (2, "/p/b.py", "b", 1, 2, "", "b", None, [0.0] * dim),
        ]
    )
    assert vec_store.entity_count() == 2
    vec_store.clear_entities()
    assert vec_store.entity_count() == 0
