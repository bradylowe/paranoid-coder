"""Integration tests for paranoid index command (RAG: summaries + entities)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from paranoid.commands.analyze import run as analyze_run
from paranoid.commands.init_cmd import run as init_run
from paranoid.commands.index_cmd import run as index_run
from paranoid.commands.summarize import run as summarize_run
from paranoid.rag.store import VectorStore


def test_index_entities_only(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Index --entities-only indexes only code entities (no summaries)."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "utils.py").write_text(
        '''
def helper(x: int) -> int:
    """Double the input."""
    return x * 2
'''
    )

    init_run(type("Args", (), {"path": tmp_path})())
    analyze_run(type("Args", (), {"path": tmp_path, "force": True, "verbose": False, "dry_run": False})())

    def mock_embed(model, texts):
        inp = texts if isinstance(texts, list) else [texts]
        return [[0.1] * 384 for _ in inp]

    with patch("paranoid.commands.index_cmd.ollama_embed", side_effect=mock_embed):
        index_run(
            type(
                "Args",
                (),
                {
                    "path": tmp_path,
                    "embedding_model": "nomic",
                    "full": False,
                    "entities_only": True,
                },
            )()
        )

    out, err = capsys.readouterr()
    assert "Indexed" in err or "entities" in err

    with VectorStore(tmp_path) as vec_store:
        entity_count = vec_store.entity_count()
        summary_count = vec_store.count()
    assert entity_count >= 1
    assert summary_count == 0


def test_index_entities_requires_analyze(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Index --entities-only exits with message when no graph (analyze not run)."""
    init_run(type("Args", (), {"path": tmp_path})())

    def mock_embed(model, texts):
        inp = texts if isinstance(texts, list) else [texts]
        return [[0.1] * 384 for _ in inp]

    with patch("paranoid.commands.index_cmd.ollama_embed", side_effect=mock_embed):
        with pytest.raises(SystemExit):
            index_run(
                type(
                    "Args",
                    (),
                    {
                        "path": tmp_path,
                        "embedding_model": "nomic",
                        "full": False,
                        "entities_only": True,
                    },
                )()
            )

    _, err = capsys.readouterr()
    assert "analyze" in err.lower() or "graph" in err.lower()

    with VectorStore(tmp_path) as vec_store:
        assert vec_store.entity_count() == 0
