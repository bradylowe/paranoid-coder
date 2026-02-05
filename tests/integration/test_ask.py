"""Integration tests for paranoid ask command (Phase 5C hybrid)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from paranoid.llm.query_classifier import ClassifiedQuery, QueryType
from paranoid.commands.analyze import run as analyze_run
from paranoid.commands.ask import run as ask_run
from paranoid.commands.init_cmd import run as init_run
from paranoid.commands.index_cmd import run as index_run
from paranoid.commands.summarize import run as summarize_run


def test_ask_usage_via_graph_no_llm(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Ask 'where is greet used?' uses graph when available, no LLM call."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "module.py").write_text(
        '''
def greet(name: str) -> str:
    """Return greeting."""
    return f"Hello, {name}"

def main() -> None:
    greet("world")
'''
    )

    init_run(type("Args", (), {"path": tmp_path})())
    analyze_run(type("Args", (), {"path": tmp_path, "force": True, "verbose": False, "dry_run": False})())

    ask_args = type(
        "Args",
        (),
        {
            "path": tmp_path,
            "question": "where is greet used?",
            "model": "qwen2.5-coder:7b",
            "embedding_model": "nomic-embed-text",
            "vector_k": 20,
            "top_k": 5,
            "sources": False,
            "force_rag": False,
            "files_only": False,
            "dirs_only": False,
        },
    )()

    # Mock classifier to return USAGE (avoids LLM call in CI)
    with patch("paranoid.commands.ask.classify_query", return_value=ClassifiedQuery(QueryType.USAGE, "greet")):
        ask_run(ask_args)

    out, err = capsys.readouterr()
    assert "main" in out or "greet" in out
    assert "called by" in out or "calls" in out


def test_ask_definition_via_graph(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Ask 'where is greet defined?' uses graph when available."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "module.py").write_text(
        '''
def greet(name: str) -> str:
    """Return greeting."""
    return f"Hello, {name}"
'''
    )

    init_run(type("Args", (), {"path": tmp_path})())
    analyze_run(type("Args", (), {"path": tmp_path, "force": True, "verbose": False, "dry_run": False})())

    ask_args = type(
        "Args",
        (),
        {
            "path": tmp_path,
            "question": "where is greet defined?",
            "model": "qwen2.5-coder:7b",
            "embedding_model": "nomic-embed-text",
            "vector_k": 20,
            "top_k": 5,
            "sources": False,
            "force_rag": False,
            "files_only": False,
            "dirs_only": False,
        },
    )()

    with patch("paranoid.commands.ask.classify_query", return_value=ClassifiedQuery(QueryType.DEFINITION, "greet")):
        ask_run(ask_args)

    out, err = capsys.readouterr()
    assert "greet" in out
    assert "Definitions" in out or "module.py" in out


def test_ask_force_rag_bypasses_graph(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """With --force-rag, usage query goes to RAG (needs summarize + index)."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "module.py").write_text(
        '''
def greet(name: str) -> str:
    """Return greeting."""
    return f"Hello, {name}"

def main() -> None:
    greet("world")
'''
    )

    init_run(type("Args", (), {"path": tmp_path})())

    # Need summarize + index for RAG path
    with patch("paranoid.commands.summarize.llm_summarize_file", side_effect=lambda *a, **kw: ("Mock summary.", None)):
        with patch("paranoid.commands.summarize.llm_summarize_directory", side_effect=lambda *a, **kw: ("Mock dir.", None)):
            summarize_run(type("Args", (), {"paths": [tmp_path], "model": "qwen", "dry_run": False, "verbose": False})())

    analyze_run(type("Args", (), {"path": tmp_path, "force": True, "verbose": False, "dry_run": False})())

    with patch("paranoid.commands.index_cmd.ollama_embed", side_effect=lambda model, texts: [[0.1] * 384 for _ in (texts if isinstance(texts, list) else [texts])]):
        index_run(type("Args", (), {"path": tmp_path, "embedding_model": "nomic", "full": False})())

    # Mock embed and generate for ask (embed returns list[float] for single str input)
    mock_embed = [0.1] * 384
    mock_answer = "Based on the summaries, greet is called by main in module.py."

    with patch("paranoid.commands.ask.classify_query", return_value=ClassifiedQuery(QueryType.EXPLANATION, None)):
        with patch("paranoid.commands.ask.ollama_embed", return_value=mock_embed):
            with patch("paranoid.commands.ask.ollama_generate", return_value=(mock_answer, None)):
                ask_args = type(
                "Args",
                (),
                {
                    "path": tmp_path,
                    "question": "where is greet used?",
                    "model": "qwen",
                    "embedding_model": "nomic",
                    "vector_k": 20,
                    "top_k": 5,
                    "sources": False,
                    "force_rag": True,
                    "files_only": False,
                    "dirs_only": False,
                },
                )()
                ask_run(ask_args)

    out, err = capsys.readouterr()
    assert "Based on the summaries" in out or "greet" in out


def test_ask_requires_summaries_for_rag(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Ask with explanation query (RAG path) exits when no summaries."""
    init_run(type("Args", (), {"path": tmp_path})())

    ask_args = type(
        "Args",
        (),
        {
            "path": tmp_path,
            "question": "explain authentication",
            "model": "qwen",
            "embedding_model": "nomic",
            "vector_k": 20,
            "top_k": 5,
            "sources": False,
            "force_rag": False,
            "files_only": False,
            "dirs_only": False,
        },
    )()

    with patch("paranoid.commands.ask.classify_query", return_value=ClassifiedQuery(QueryType.EXPLANATION, "authentication")):
        with pytest.raises(SystemExit) as exc_info:
            ask_run(ask_args)
    assert exc_info.value.code != 0

    _, err = capsys.readouterr()
    assert "summarize" in err.lower()
