"""Code entity data models for static analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EntityType(Enum):
    """Types of code entities we extract."""

    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    MODULE = "module"


@dataclass
class CodeEntity:
    """Represents a code entity (class, function, method)."""

    file_path: str  # Absolute path to file (normalized posix)
    type: EntityType
    name: str
    qualified_name: str
    parent_name: Optional[str] = None  # Parent class name (for methods)

    lineno: int = 0
    end_lineno: int = 0
    docstring: Optional[str] = None
    signature: Optional[str] = None

    language: str = "python"

    # Set after DB insert
    id: Optional[int] = None
    parent_entity_id: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "file_path": self.file_path,
            "type": self.type.value,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "parent_name": self.parent_name,
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
            "docstring": self.docstring,
            "signature": self.signature,
            "language": self.language,
        }
