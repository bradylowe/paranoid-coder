"""Data models for storage (Summary, IgnorePattern) matching project_plan schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Summary:
    """A single file or directory summary stored in the database."""

    path: str  # Absolute normalized path (e.g. .as_posix())
    type: str  # 'file' or 'directory'
    hash: str  # SHA-256 of file content or folder tree
    description: str  # LLM-generated summary
    file_extension: Optional[str] = None  # e.g. ".py", None for directories
    error: Optional[str] = None  # Error message if summarization failed
    needs_update: bool = False

    # Model metadata
    model: str = ""
    model_version: Optional[str] = None
    prompt_version: str = ""
    context_level: int = 0  # 0=isolated, 1=with-parent, 2=with-rag

    # Timestamps (ISO format or datetime)
    generated_at: str = ""
    updated_at: str = ""

    # Optional metrics
    tokens_used: Optional[int] = None
    generation_time_ms: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.generated_at and self.updated_at:
            self.generated_at = self.updated_at
        if not self.updated_at and self.generated_at:
            self.updated_at = self.generated_at


@dataclass
class IgnorePattern:
    """An ignore pattern (e.g. from .paranoidignore) stored in the database."""

    pattern: str
    added_at: str  # ISO timestamp
    source: Optional[str] = None  # 'file' (.paranoidignore) or 'command' (CLI)
    id: Optional[int] = None  # Set after insert (AUTOINCREMENT)


@dataclass
class ProjectStats:
    """Aggregated summary statistics from the database."""

    count_by_type: dict[str, int]  # 'file' -> n, 'directory' -> n
    last_updated_at: Optional[str] = None  # ISO timestamp of most recent update
    model_breakdown: list[tuple[str, int]] = field(default_factory=list)  # [(model_name, count), ...]
