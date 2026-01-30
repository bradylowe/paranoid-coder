"""Versioned prompt templates for file and directory summaries (context_level 0: isolated)."""

from __future__ import annotations

# Bump when prompt wording or structure changes; stored with each summary.
PROMPT_VERSION = "v1"


def description_length_for_content(content: str) -> str:
    """
    Return expected summary length hint based on input size (characters).
    Used so the model produces appropriately sized responses.
    """
    n = len(content)
    if n < 5000:
        return "a few lines"
    if n < 15000:
        return "1-3 paragraphs"
    return "3-5 paragraphs"


def file_summary_prompt(
    file_path: str,
    content: str,
    existing_summary: str | None = None,
) -> str:
    """
    Build prompt for summarizing a single file (context_level 0: isolated).
    No parent or sibling context; first-pass / isolated summary.
    """
    description_length = description_length_for_content(content)
    existing = (existing_summary or "None").strip()
    prompt = (
        f"Generate a concise description ({description_length}) for this file.\n"
        f"File: {file_path}\n\n"
        f"Content:\n{content}\n\n"
        f"Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n"
        f"Focus: purpose, main functions/classes, important logic, notable patterns."
    )
    return prompt


def directory_summary_prompt(
    dir_path: str,
    children_text: str,
    existing_summary: str | None = None,
    is_root: bool = False,
) -> str:
    """
    Build prompt for summarizing a directory from its children's summaries.
    context_level 0: no extra context beyond children list.
    """
    n_paragraphs = "5-10" if is_root else "1-5"
    existing = (existing_summary or "None").strip()
    prompt = (
        f"Create or improve a concise directory description ({n_paragraphs} paragraphs).\n"
        f"Directory: {dir_path}\n\n"
        f"Direct children (name: summary):\n{children_text or '(empty)'}\n\n"
        f"Previous description (improve if present):\n{existing}\n\n"
        f"Focus: overall purpose, how pieces work together, main responsibilities."
    )
    return prompt
