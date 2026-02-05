"""Ollama client: generate wrapper with context sizing and connection error handling."""

from __future__ import annotations

from typing import Any

import ollama

from paranoid.llm.context import ContextOverflowException, get_context_size


class OllamaConnectionError(Exception):
    """Raised when Ollama is unreachable (connection refused, timeout, etc.)."""


def generate_simple(
    prompt: str,
    model: str,
    options: dict[str, Any] | None = None,
) -> str:
    """
    Simple generate call for short responses (e.g. query classification).
    Returns response text only. Uses minimal context for speed.
    Raises OllamaConnectionError if Ollama is unreachable.
    """
    opts = dict(options) if options else {}
    opts.setdefault("num_ctx", 2048)
    opts.setdefault("num_predict", 16)
    opts.setdefault("temperature", 0)
    try:
        response = ollama.generate(model=model, prompt=prompt, options=opts)
    except (ConnectionError, TimeoutError, OSError) as e:
        raise OllamaConnectionError(f"Ollama unreachable: {e}") from e
    return (response.get("response") or "").strip()


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


def embed(model: str, input_text: str | list[str]) -> list[float] | list[list[float]]:
    """
    Get embedding(s) from Ollama for the given text(s).

    Returns a single list of floats if input_text is str, or a list of lists if input_text is list.
    Raises OllamaConnectionError if Ollama is unreachable.
    """
    try:
        response = ollama.embed(model=model, input=input_text)
    except (ConnectionError, TimeoutError, OSError) as e:
        raise OllamaConnectionError(f"Ollama unreachable: {e}") from e
    raw = response.get("embeddings")
    if raw is None:
        raise ValueError("Ollama embed response missing 'embeddings'")
    # Each item may be a list of floats or a dict with 'embedding' key (Pydantic model)
    def to_list(item: Any) -> list[float]:
        if hasattr(item, "embedding"):
            return list(item.embedding)
        return list(item)

    embeddings = [to_list(e) for e in raw]
    if isinstance(input_text, str):
        if len(embeddings) != 1:
            raise ValueError("Expected single embedding for single input")
        return embeddings[0]
    return embeddings
