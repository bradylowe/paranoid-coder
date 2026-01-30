"""Context window sizing for Ollama generate calls."""

from __future__ import annotations

# Power-of-2 context sizes: minimum 16k, maximum 128k (2**17)
CONTEXT_MIN = 2**14   # 16384
CONTEXT_MAX = 2**17   # 131072

# Chars per token estimate for code-heavy prompts
CHARS_PER_TOKEN = 3

# Response token budget: 2k for smaller prompts, 4k for larger
RESPONSE_TOKENS_SMALL = 2048
RESPONSE_TOKENS_LARGE = 4096
RESPONSE_TOKENS_SMALL_THRESHOLD = 16384


class ContextOverflowException(Exception):
    """Raised when estimated prompt + response tokens exceed maximum context (2**17)."""


def get_context_size(prompt: str) -> int:
    """
    Compute the context window size (num_ctx) for an Ollama generate call.

    Uses a conservative ~3 chars/token for code-heavy prompts. Reserves 2k–4k
    tokens for the response. Returns the smallest power-of-2 context in
    [2**14, 2**15, 2**16, 2**17] that fits. Raises ContextOverflowException
    if estimated total exceeds 2**17.
    """
    estimated_tokens = len(prompt) // CHARS_PER_TOKEN
    response_tokens = (
        RESPONSE_TOKENS_SMALL
        if estimated_tokens < RESPONSE_TOKENS_SMALL_THRESHOLD
        else RESPONSE_TOKENS_LARGE
    )
    total_tokens_needed = estimated_tokens + response_tokens

    if total_tokens_needed <= CONTEXT_MIN:
        return CONTEXT_MIN
    if total_tokens_needed <= 2**15:
        return 2**15
    if total_tokens_needed <= 2**16:
        return 2**16
    if total_tokens_needed <= CONTEXT_MAX:
        return CONTEXT_MAX

    raise ContextOverflowException(
        f"Estimated tokens ({total_tokens_needed:.0f}) exceeds maximum context ({CONTEXT_MAX})"
    )
