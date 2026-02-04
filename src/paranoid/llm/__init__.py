"""LLM integration (Ollama client, prompts, context sizing)."""

from __future__ import annotations

from paranoid.llm.context import ContextOverflowException, get_context_size
from paranoid.llm.ollama import OllamaConnectionError, summarize as _generate
from paranoid.llm.prompts import (
    PROMPT_VERSION,
    description_length_for_content,
    detect_directory_language,
    detect_language,
    directory_summary_prompt,
    file_summary_prompt,
)


def summarize_file(
    file_path: str,
    content: str,
    model: str,
    existing_summary: str | None = None,
    language: str | None = None,
    graph_context: str | None = None,
) -> tuple[str, str | None]:
    """
    Summarize a file. Returns (summary_text, model_version).
    If graph_context is provided (from code graph), includes it for context-rich summarization.
    Raises ContextOverflowException or OllamaConnectionError.
    """
    prompt = file_summary_prompt(
        file_path,
        content,
        existing_summary=existing_summary,
        language=language,
        graph_context=graph_context,
    )
    return _generate(prompt, model)


def summarize_directory(
    dir_path: str,
    children_text: str,
    model: str,
    existing_summary: str | None = None,
    is_root: bool = False,
    primary_language: str | None = None,
) -> tuple[str, str | None]:
    """
    Summarize a directory from its children's summaries (context_level 0).
    Uses language-specific prompt when primary_language is provided.
    Returns (summary_text, model_version). Raises ContextOverflowException or OllamaConnectionError.
    """
    prompt = directory_summary_prompt(
        dir_path,
        children_text,
        existing_summary=existing_summary,
        is_root=is_root,
        primary_language=primary_language,
    )
    return _generate(prompt, model)


__all__ = [
    "ContextOverflowException",
    "OllamaConnectionError",
    "PROMPT_VERSION",
    "description_length_for_content",
    "detect_directory_language",
    "detect_language",
    "directory_summary_prompt",
    "file_summary_prompt",
    "get_context_size",
    "summarize_directory",
    "summarize_file",
]
