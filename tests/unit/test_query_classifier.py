"""Unit tests for query classifier (Phase 5C - LLM-based routing)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from paranoid.llm.query_classifier import (
    ClassifiedQuery,
    QueryRouter,
    QueryType,
    TEST_CASES,
    classify_query,
    _extract_entity,
    _parse_category,
)


def test_parse_category() -> None:
    """Category parsing handles LLM output variations."""
    assert _parse_category("USAGE") == QueryType.USAGE
    assert _parse_category("usage") == QueryType.USAGE
    assert _parse_category("DEFINITION") == QueryType.DEFINITION
    assert _parse_category("EXPLANATION") == QueryType.EXPLANATION
    assert _parse_category("GENERATION") == QueryType.GENERATION
    assert _parse_category("USAGE\n") == QueryType.USAGE
    assert _parse_category("USAGE extra text") == QueryType.USAGE
    assert _parse_category("") == QueryType.EXPLANATION
    assert _parse_category("unknown") == QueryType.EXPLANATION


def test_extract_entity() -> None:
    """Entity extraction from query text."""
    assert _extract_entity("where is greet used?") == "greet"
    assert _extract_entity("Who calls User.login?") == "User.login"
    assert _extract_entity("find the authenticate function") == "authenticate"
    assert _extract_entity("explain how JWT validation works") == "JWT"
    assert _extract_entity("how does Parser work?") == "Parser"
    assert _extract_entity("write a test for login") is None


def test_classify_with_mock_llm() -> None:
    """Classification uses LLM and returns correct type."""
    responses = ["USAGE", "DEFINITION", "EXPLANATION", "GENERATION"]

    def mock_generate(prompt, model, options=None):
        return responses.pop(0)

    router = QueryRouter(classifier_model="test-model", generate_fn=mock_generate)

    c = router.classify("where is User.login called?")
    assert c.query_type == QueryType.USAGE
    assert c.entity_name == "User.login"

    c = router.classify("find the authenticate function")
    assert c.query_type == QueryType.DEFINITION
    assert c.entity_name == "authenticate"

    c = router.classify("explain how JWT validation works")
    assert c.query_type == QueryType.EXPLANATION
    assert c.entity_name == "JWT"

    c = router.classify("write a test for login")
    assert c.query_type == QueryType.GENERATION
    assert c.entity_name is None


def test_classify_fallback_on_error() -> None:
    """On LLM error, falls back to EXPLANATION with entity extraction."""
    def failing_generate(*args, **kwargs):
        raise ConnectionError("Ollama unreachable")

    router = QueryRouter(classifier_model="test", generate_fn=failing_generate)
    c = router.classify("where is greet used?")
    assert c.query_type == QueryType.EXPLANATION
    assert c.entity_name == "greet"


def test_test_cases_validation() -> None:
    """Validate classifier against known test cases (with mocked LLM)."""
    call_count = [0]
    responses = ["USAGE", "DEFINITION", "EXPLANATION", "GENERATION"]

    def mock_generate(prompt, model, options=None):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return responses[idx]

    router = QueryRouter(classifier_model="test", generate_fn=mock_generate)
    correct = 0
    for query, exp in TEST_CASES:
        result = router.classify(query)
        if result.query_type == exp:
            correct += 1
    accuracy = correct / len(TEST_CASES)
    assert accuracy >= 0.9, f"Classifier accuracy {accuracy} below threshold"


def test_classify_query_integration() -> None:
    """classify_query uses config and returns ClassifiedQuery."""
    import paranoid.llm.query_classifier as qc

    qc._default_router = None  # Reset to force fresh router
    with patch("paranoid.llm.ollama.generate_simple", return_value="USAGE") as mock_gen:
        c = classify_query("where is greet called?", config={"default_classifier_model": "qwen2.5-coder-cpu:1.5b"})
        assert c.query_type == QueryType.USAGE
        assert c.entity_name == "greet"
        assert mock_gen.called
