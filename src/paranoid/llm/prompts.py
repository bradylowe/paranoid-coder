"""Versioned prompt templates for file and directory summaries (context_level 0: isolated)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from paranoid.storage.models import Summary

# Bump when prompt wording or structure changes; stored with each summary.
PROMPT_VERSION = "v2"

# Extension (lowercase, with dot) -> language key for prompts
LANGUAGE_MAP = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript-react",
    ".tsx": "typescript-react",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".md": "markdown",
    ".mdx": "markdown",
    ".txt": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".r": "r",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".sql": "sql",
    ".vue": "vue",
    ".svelte": "svelte",
}


def detect_language(filepath: str | Path) -> str:
    """Return language key for a file path based on extension. 'unknown' if not mapped."""
    ext = Path(filepath).suffix.lower()
    return LANGUAGE_MAP.get(ext, "unknown")


def detect_directory_language(children: list[Summary]) -> str:
    """Determine primary language of directory based on file children. Returns 'unknown' if no files."""
    file_children = [c for c in children if c.type == "file"]
    language_counts: Counter[str] = Counter()
    for c in file_children:
        lang = (c.language or "unknown").strip() or "unknown"
        language_counts[lang] += 1
    if not language_counts:
        return "unknown"
    return language_counts.most_common(1)[0][0]


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


# Language-specific prompt templates. Use {filename}, {content}, {children}, {extension}, {length}, {n_paragraphs}, {existing}.
PROMPTS = {
    "python": {
        "file": "Generate a concise description ({length}) for this Python file.\n"
        "Focus: purpose, main classes/functions, dependencies, patterns.\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this Python module/package ({n_paragraphs} paragraphs).\n"
        "Focus: overall purpose, how components interact.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "javascript": {
        "file": "Generate a concise description ({length}) for this JavaScript file.\n"
        "Focus: exports, main functions, React components (if any), side effects.\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this JavaScript module ({n_paragraphs} paragraphs).\n"
        "Focus: module purpose, component hierarchy, dependencies.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "typescript": {
        "file": "Generate a concise description ({length}) for this TypeScript file.\n"
        "Focus: types, exports, main functions, React components (if any).\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this TypeScript module ({n_paragraphs} paragraphs).\n"
        "Focus: module purpose, types, component hierarchy.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "javascript-react": {
        "file": "Generate a concise description ({length}) for this JSX file.\n"
        "Focus: React components, props, exports, hooks.\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this JavaScript/React module ({n_paragraphs} paragraphs).\n"
        "Focus: component structure, hierarchy, dependencies.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "typescript-react": {
        "file": "Generate a concise description ({length}) for this TSX file.\n"
        "Focus: React components, types, props, exports, hooks.\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this TypeScript/React module ({n_paragraphs} paragraphs).\n"
        "Focus: component structure, types, hierarchy.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "go": {
        "file": "Generate a concise description ({length}) for this Go file.\n"
        "Focus: package, exported symbols, main types/functions, concurrency.\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this Go package ({n_paragraphs} paragraphs).\n"
        "Focus: package purpose, public API, how files interact.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "rust": {
        "file": "Generate a concise description ({length}) for this Rust file.\n"
        "Focus: modules, public items, main types/functions, traits.\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this Rust module/crate ({n_paragraphs} paragraphs).\n"
        "Focus: module structure, public API, dependencies.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "java": {
        "file": "Generate a concise description ({length}) for this Java file.\n"
        "Focus: classes, main methods, package, dependencies.\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this Java package ({n_paragraphs} paragraphs).\n"
        "Focus: package purpose, main classes, structure.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "markdown": {
        "file": "Summarize this documentation file ({length}).\n"
        "Focus: main topics, key information, intended audience.\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this directory ({n_paragraphs} paragraphs).\n"
        "Focus: overall purpose, how pieces work together.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "text": {
        "file": "Describe this text file ({length}).\n"
        "Focus: purpose, structure, notable content.\n"
        "File: {filename}\n\n{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this directory ({n_paragraphs} paragraphs).\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
    "unknown": {
        "file": "Describe this file ({extension}) ({length}).\n"
        "Focus: apparent purpose, structure, notable content.\n"
        "{content}\n\n"
        "Existing summary (improve if present, or write from scratch if None):\n{existing}\n\n",
        "directory": "Describe this directory ({n_paragraphs} paragraphs).\n"
        "Focus: overall purpose, how pieces work together.\n"
        "Directory: {dir_path}\n\nDirect children (name: summary):\n{children}\n\n"
        "Previous description (improve if present):\n{existing}\n\n",
    },
}

# Fallback directory prompt when language has no directory template (use unknown)
DEFAULT_DIRECTORY_PROMPT = PROMPTS["unknown"]["directory"]


def file_summary_prompt(
    file_path: str,
    content: str,
    existing_summary: str | None = None,
    language: str | None = None,
) -> str:
    """
    Build prompt for summarizing a single file (context_level 0: isolated).
    Uses language-specific template if language is provided and mapped; otherwise detects from path.
    """
    lang = language or detect_language(file_path)
    template = PROMPTS.get(lang, PROMPTS["unknown"])["file"]
    length = description_length_for_content(content)
    existing = (existing_summary or "None").strip()
    filename = Path(file_path).name
    ext = Path(file_path).suffix.lower() or "(none)"
    return template.format(
        filename=filename,
        content=content,
        existing=existing,
        length=length,
        extension=ext,
    )


def directory_summary_prompt(
    dir_path: str,
    children_text: str,
    existing_summary: str | None = None,
    is_root: bool = False,
    primary_language: str | None = None,
) -> str:
    """
    Build prompt for summarizing a directory from its children's summaries.
    Uses language-specific template when primary_language is provided; otherwise falls back to unknown.
    """
    lang = primary_language or "unknown"
    template = PROMPTS.get(lang, PROMPTS["unknown"]).get("directory", DEFAULT_DIRECTORY_PROMPT)
    n_paragraphs = "5-10" if is_root else "1-5"
    existing = (existing_summary or "None").strip()
    return template.format(
        dir_path=dir_path,
        children=children_text or "(empty)",
        existing=existing,
        n_paragraphs=n_paragraphs,
    )
