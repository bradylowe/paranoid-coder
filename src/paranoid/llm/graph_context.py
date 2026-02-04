"""Build graph context for summarization prompts (imports, exports, callers, callees)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paranoid.storage.base import StorageBase


SUMMARY_CONTEXT_VERSION = "1"


@dataclass
class FileContextSnapshot:
    """Snapshot of graph context for a file (used for smart invalidation)."""

    imports_hash: str
    callers_count: int
    callees_count: int


def compute_file_context_snapshot(storage: StorageBase, file_path: str) -> FileContextSnapshot | None:
    """
    Compute current context snapshot (imports_hash, callers_count, callees_count) for a file.
    Returns None if no graph data exists.
    """
    get_imports = getattr(storage, "get_imports_for_file", None)
    get_entities = getattr(storage, "get_entities_by_file", None)
    get_callers = getattr(storage, "get_callers_of_entity", None)
    get_callees = getattr(storage, "get_callees_of_entity", None)
    if not all([get_imports, get_entities, get_callers, get_callees]):
        return None

    imports = get_imports(file_path)
    entities = get_entities(file_path)
    if not imports and not entities:
        return None

    imports_hash = hashlib.sha256(",".join(sorted(set(imports))).encode()).hexdigest()
    callers_count = 0
    callees_count = 0
    for ent in entities:
        if ent.id is not None:
            callers_count += len(get_callers(ent.id))
            callees_count += len(get_callees(ent.id))

    return FileContextSnapshot(
        imports_hash=imports_hash,
        callers_count=callers_count,
        callees_count=callees_count,
    )


def build_graph_context_for_file(storage: StorageBase, file_path: str) -> str | None:
    """
    Build a formatted graph context string for a file (imports, exports, callers, callees).
    Returns None if no graph data exists (e.g. `paranoid analyze` not run).
    """
    get_imports = getattr(storage, "get_imports_for_file", None)
    get_entities = getattr(storage, "get_entities_by_file", None)
    get_callers = getattr(storage, "get_callers_of_entity", None)
    get_callees = getattr(storage, "get_callees_of_entity", None)
    if not all([get_imports, get_entities, get_callers, get_callees]):
        return None

    imports = get_imports(file_path)
    entities = get_entities(file_path)
    if not imports and not entities:
        return None

    lines: list[str] = []
    lines.append("Code graph context:")

    if imports:
        lines.append("  Imports: " + ", ".join(sorted(set(imports))))

    if entities:
        exports = [e.qualified_name for e in entities]
        lines.append("  Exports: " + ", ".join(exports))

        for ent in entities:
            if ent.id is None:
                continue
            callers = get_callers(ent.id)
            callees = get_callees(ent.id)
            if callers or callees:
                parts: list[str] = []
                if callers:
                    caller_names = [c[0] for c in callers[:5]]  # Limit for brevity
                    if len(callers) > 5:
                        caller_names.append(f"...+{len(callers) - 5} more")
                    parts.append(f"callers=[{', '.join(caller_names)}]")
                if callees:
                    callee_names = [c[0] for c in callees[:5]]
                    if len(callees) > 5:
                        callee_names.append(f"...+{len(callees) - 5} more")
                    parts.append(f"callees=[{', '.join(callee_names)}]")
                lines.append(f"  {ent.qualified_name}: " + ", ".join(parts))

    return "\n".join(lines) if len(lines) > 1 else None
