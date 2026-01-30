"""Abstract Storage interface for summaries and metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

from paranoid.storage.models import IgnorePattern, ProjectStats, Summary


@runtime_checkable
class Storage(Protocol):
    """Protocol for storage backends (e.g. SQLite)."""

    def get_summary(self, path: Path | str) -> Summary | None:
        """Return the summary for the given path, or None if not found."""
        ...

    def set_summary(self, summary: Summary) -> None:
        """Insert or replace a summary (upsert by path)."""
        ...

    def delete_summary(self, path: Path | str) -> None:
        """Remove the summary for the given path. No-op if not present."""
        ...

    def list_children(self, path: Path | str) -> list[Summary]:
        """Return direct children (files and dirs) of the given directory path."""
        ...

    def get_metadata(self, key: str) -> str | None:
        """Return metadata value for key, or None."""
        ...

    def set_metadata(self, key: str, value: str) -> None:
        """Set metadata key to value."""
        ...

    def add_ignore_pattern(self, pattern: str, source: str) -> None:
        """Record an ignore pattern with source ('file' or 'command')."""
        ...

    def set_ignore_patterns_for_source(self, source: str, patterns: list[str]) -> None:
        """Replace all patterns for the given source with the new list (for syncing file-based patterns)."""
        ...

    def get_ignore_patterns(self) -> list[IgnorePattern]:
        """Return all stored ignore patterns."""
        ...

    def get_stats(self, scope_path: str | None = None) -> ProjectStats:
        """Return aggregated stats (count by type, last update, model breakdown), optionally scoped to path prefix."""
        ...


class StorageBase(ABC):
    """Abstract base class for storage implementations."""

    @abstractmethod
    def get_summary(self, path: Path | str) -> Summary | None:
        """Return the summary for the given path, or None if not found."""
        ...

    @abstractmethod
    def set_summary(self, summary: Summary) -> None:
        """Insert or replace a summary (upsert by path)."""
        ...

    @abstractmethod
    def delete_summary(self, path: Path | str) -> None:
        """Remove the summary for the given path. No-op if not present."""
        ...

    @abstractmethod
    def list_children(self, path: Path | str) -> list[Summary]:
        """Return direct children (files and dirs) of the given directory path."""
        ...

    @abstractmethod
    def get_metadata(self, key: str) -> str | None:
        """Return metadata value for key, or None."""
        ...

    @abstractmethod
    def set_metadata(self, key: str, value: str) -> None:
        """Set metadata key to value."""
        ...

    @abstractmethod
    def add_ignore_pattern(self, pattern: str, source: str) -> None:
        """Record an ignore pattern with source ('file' or 'command')."""
        ...

    @abstractmethod
    def set_ignore_patterns_for_source(self, source: str, patterns: list[str]) -> None:
        """Replace all patterns for the given source with the new list (for syncing file-based patterns)."""
        ...

    @abstractmethod
    def get_ignore_patterns(self) -> list[IgnorePattern]:
        """Return all stored ignore patterns."""
        ...

    @abstractmethod
    def get_stats(self, scope_path: str | None = None) -> ProjectStats:
        """Return aggregated stats (count by type, last update, model breakdown), optionally scoped to path prefix."""
        ...
