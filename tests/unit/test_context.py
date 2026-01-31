"""Unit tests for LLM context sizing (get_context_size, ContextOverflowException)."""

from __future__ import annotations

import pytest

from paranoid.llm.context import (
    CONTEXT_MAX,
    CONTEXT_MIN,
    ContextOverflowException,
    get_context_size,
)


def test_get_context_size_small_prompt() -> None:
    """Short prompt uses CONTEXT_MIN (16k)."""
    prompt = "x" * 100
    assert get_context_size(prompt) == CONTEXT_MIN


def test_get_context_size_medium_prompt() -> None:
    """Prompt that needs more than 16k but fits in 32k returns 2**15."""
    # ~3 chars/token, 2k response -> need ~16k + 6k = 22k input to exceed 16k? Actually
    # total_tokens_needed = estimated_tokens + response_tokens. estimated_tokens = len/3.
    # For CONTEXT_MIN we need total_tokens_needed <= 16384. So estimated_tokens + 2048 <= 16384 -> estimated <= 14336 -> len <= 43008.
    prompt_small = "x" * 10000  # ~3333 tokens + 2048 = 5381 -> CONTEXT_MIN
    assert get_context_size(prompt_small) == CONTEXT_MIN
    # Push past 16k total: need estimated + 2048 > 16384 -> estimated > 14336 -> len > 43008
    prompt_medium = "x" * 50000  # ~16666 tokens + 2048 = 18714 -> need 2**15
    assert get_context_size(prompt_medium) == 2**15


def test_get_context_size_large_prompt() -> None:
    """Larger prompt gets 2**16 or 2**17."""
    prompt = "x" * 100000
    size = get_context_size(prompt)
    assert size in (2**15, 2**16, 2**17)


def test_get_context_size_max() -> None:
    """Prompt that fits in CONTEXT_MAX returns CONTEXT_MAX."""
    # Stay under overflow: CONTEXT_MAX = 131072. We need estimated_tokens + response_tokens <= 131072.
    # With RESPONSE_TOKENS_LARGE = 4096, estimated <= 126976 -> len <= 380928
    prompt = "x" * 380000
    assert get_context_size(prompt) == CONTEXT_MAX


def test_get_context_size_overflow() -> None:
    """Very large prompt raises ContextOverflowException."""
    # Exceed 128k: need estimated_tokens + 4096 > 131072 -> estimated > 126976 -> len > 380928
    huge = "x" * 400000
    with pytest.raises(ContextOverflowException) as exc_info:
        get_context_size(huge)
    assert "131072" in str(exc_info.value) or "exceeds" in str(exc_info.value).lower()
