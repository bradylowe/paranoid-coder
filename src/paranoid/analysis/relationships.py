"""Code relationship data models for static analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RelationshipType(Enum):
    """Types of relationships between code entities."""

    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    INSTANTIATES = "instantiates"
    DEFINES = "defines"


@dataclass
class Relationship:
    """Represents a relationship between entities or files."""

    relationship_type: RelationshipType

    from_entity_id: Optional[int] = None
    to_entity_id: Optional[int] = None
    from_file: Optional[str] = None
    to_file: Optional[str] = None  # For imports: module path; for calls/inherits: target name
    location: Optional[str] = None  # "file.py:42"

    # Resolution hint (used before storage, not persisted):
    # Qualified name of the source entity (for CALLS/INHERITS) to resolve from_entity_id
    from_entity_qualified_name: Optional[str] = None

    id: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "relationship_type": self.relationship_type.value,
            "from_entity_id": self.from_entity_id,
            "to_entity_id": self.to_entity_id,
            "from_file": self.from_file,
            "to_file": self.to_file,
            "location": self.location,
        }
