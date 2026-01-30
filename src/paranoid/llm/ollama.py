"""Ollama client: generate wrapper with context sizing and connection error handling."""

from __future__ import annotations

from typing import Any

import ollama

from paranoid.llm.context import ContextOverflowException, get_context_size


class OllamaConnectionError(Exception):
    """Raised when Ollama is unreachable (connection refused, timeout, etc.)."""


def summarize(
    prompt: str,
    model: str,
    options: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    """
    Send prompt to Ollama and return (response_text, model_version).

    Computes num_ctx from prompt size (min 16k, up to 128k; 2k–4k tokens for response).
    Raises ContextOverflowException if prompt + response would exceed 128k tokens.
    Raises OllamaConnectionError if Ollama is unreachable.
    """
    try:
        num_ctx = get_context_size(prompt)
    except ContextOverflowException:
        raise
    opts = dict(options) if options else {}
    opts["num_ctx"] = num_ctx
    try:
        response = ollama.generate(model=model, prompt=prompt, options=opts)
    except (ConnectionError, TimeoutError, OSError) as e:
        raise OllamaConnectionError(f"Ollama unreachable: {e}") from e
    text = (response.get("response") or "").strip()
    # Ollama response may include 'model' (name); use as model_version if no digest
    model_version = response.get("model")
    return text, model_version
