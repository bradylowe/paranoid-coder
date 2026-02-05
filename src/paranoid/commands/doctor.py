"""Doctor command: scan entities for documentation quality (Phase 5B)."""

from __future__ import annotations

import json
import re
import sys
from argparse import Namespace
from dataclasses import dataclass, field
from pathlib import Path

from paranoid.analysis.entities import CodeEntity
from paranoid.config import require_project_root
from paranoid.graph import GraphQueries
from paranoid.storage import SQLiteStorage


@dataclass
class DocQualityResult:
    """Documentation quality assessment for an entity."""

    entity: CodeEntity
    has_docstring: bool
    has_examples: bool
    has_type_hints: bool
    priority_score: int
    callers_count: int
    lines: int
    is_public: bool


def _has_docstring(entity: CodeEntity) -> bool:
    """True if entity has a non-empty docstring."""
    doc = entity.docstring
    return bool(doc and doc.strip())


def _has_examples(docstring: str | None) -> bool:
    """
    Heuristic: docstring contains examples.
    Looks for 'Example', '>>>', '```', or 'e.g.'.
    """
    if not docstring or not docstring.strip():
        return False
    doc_lower = docstring.lower()
    return (
        "example" in doc_lower
        or ">>>" in docstring
        or "```" in docstring
        or " e.g. " in doc_lower
        or "e.g.," in doc_lower
    )


def _has_type_hints(entity: CodeEntity) -> bool:
    """
    Heuristic: signature suggests type hints.
    Python: '->' (return) or ': ' in params; JS/TS: ': type' patterns.
    """
    sig = entity.signature
    if not sig:
        return False
    # Python return type
    if "->" in sig:
        return True
    # Python param: name: Type
    if re.search(r":\s*\w+", sig):
        return True
    # TypeScript/JS: : Type in params
    if re.search(r"\)\s*:\s*\w+", sig):
        return True
    return False


def _is_public_api(entity: CodeEntity) -> bool:
    """True if entity is part of public API (not name starting with _)."""
    return not entity.name.startswith("_")


def _compute_priority_score(
    callers_count: int,
    lines: int,
    is_public: bool,
) -> int:
    """
    Priority = usage × complexity × public API factor.
    Bounded to keep scores manageable.
    """
    usage = 1 + min(callers_count, 9)  # 1-10
    complexity = 1 + min(max(lines, 0) // 5, 9)  # 1-10, every 5 lines
    public_factor = 2 if is_public else 1
    return usage * complexity * public_factor


def _scan_entities(
    storage: SQLiteStorage,
    gq: GraphQueries,
    scope_path: str | None,
) -> list[DocQualityResult]:
    """Scan all entities and compute documentation quality metrics."""
    entities = storage.get_all_entities(scope_path=scope_path)
    results: list[DocQualityResult] = []

    for entity in entities:
        if entity.id is None:
            continue

        callers = gq.get_callers(entity)
        callers_count = len(callers)
        lines = max(0, (entity.end_lineno or entity.lineno) - entity.lineno + 1)
        is_public = _is_public_api(entity)
        has_doc = _has_docstring(entity)
        has_ex = _has_examples(entity.docstring)
        has_types = _has_type_hints(entity)
        priority = _compute_priority_score(callers_count, lines, is_public)

        results.append(
            DocQualityResult(
                entity=entity,
                has_docstring=has_doc,
                has_examples=has_ex,
                has_type_hints=has_types,
                priority_score=priority,
                callers_count=callers_count,
                lines=lines,
                is_public=is_public,
            )
        )

        # Optionally persist to doc_quality table
        storage.set_doc_quality(
            entity_id=entity.id,
            has_docstring=has_doc,
            has_examples=has_ex,
            has_type_hints=has_types,
            priority_score=priority,
        )

    return results


def _result_to_dict(r: DocQualityResult) -> dict:
    """Convert result to JSON-serializable dict."""
    e = r.entity
    return {
        "qualified_name": e.qualified_name,
        "name": e.name,
        "type": e.type.value,
        "file_path": e.file_path,
        "lineno": e.lineno,
        "has_docstring": r.has_docstring,
        "has_examples": r.has_examples,
        "has_type_hints": r.has_type_hints,
        "priority_score": r.priority_score,
        "callers_count": r.callers_count,
        "lines": r.lines,
        "is_public": r.is_public,
    }


def _print_report(
    results: list[DocQualityResult],
    top_n: int | None,
    show_all_issues: bool = True,
) -> None:
    """Print human-readable report to stdout."""
    # Sort by priority descending
    sorted_results = sorted(results, key=lambda r: r.priority_score, reverse=True)
    if top_n is not None:
        sorted_results = sorted_results[:top_n]

    if not sorted_results:
        print("No entities found. Run `paranoid analyze .` first.")
        return

    missing_doc = [r for r in sorted_results if not r.has_docstring]
    missing_examples = [r for r in sorted_results if r.has_docstring and not r.has_examples]
    missing_types = [r for r in sorted_results if not r.has_type_hints]

    print("Documentation quality report")
    print()
    print(f"  Total entities scanned: {len(results)}")
    if top_n is not None:
        print(f"  Showing top {top_n} by priority")
    print()

    if show_all_issues:
        if missing_doc:
            print("  Missing docstrings (by priority):")
            for r in missing_doc[:20]:
                loc = f"{r.entity.file_path}:{r.entity.lineno}"
                print(f"    [{r.priority_score:4d}] {r.entity.qualified_name}  ({loc})")
            if len(missing_doc) > 20:
                print(f"    ... and {len(missing_doc) - 20} more")
            print()

        if missing_examples:
            print("  Has docstring but no examples (by priority):")
            for r in missing_examples[:10]:
                loc = f"{r.entity.file_path}:{r.entity.lineno}"
                print(f"    [{r.priority_score:4d}] {r.entity.qualified_name}  ({loc})")
            if len(missing_examples) > 10:
                print(f"    ... and {len(missing_examples) - 10} more")
            print()

    print("  Top items by priority (need attention):")
    for r in sorted_results[:15]:
        issues: list[str] = []
        if not r.has_docstring:
            issues.append("no docstring")
        elif not r.has_examples:
            issues.append("no examples")
        if not r.has_type_hints:
            issues.append("no type hints")
        issue_str = "; ".join(issues) if issues else "OK"
        loc = f"{r.entity.file_path}:{r.entity.lineno}"
        print(f"    [{r.priority_score:4d}] {r.entity.qualified_name}  ({loc})  [{issue_str}]")


def run(args: Namespace) -> None:
    """Run the doctor command."""
    path: Path = getattr(args, "path", Path("."))
    project_root = require_project_root(path)

    top_n = getattr(args, "top", None)
    fmt = getattr(args, "format", "text")
    scope_path = path.resolve().as_posix()

    storage = SQLiteStorage(project_root)
    with storage:
        for msg in storage.get_migration_messages():
            print(f"Note: {msg}", file=sys.stderr)

        # Check that we have entities (analyze has been run)
        entities = storage.get_all_entities(scope_path=scope_path)
        if not entities:
            print(
                "No code entities found. Run `paranoid analyze .` first to extract the code graph.",
                file=sys.stderr,
            )
            sys.exit(1)

        gq = GraphQueries(storage, project_root)
        results = _scan_entities(storage, gq, scope_path)

    if fmt == "json":
        sorted_results = sorted(results, key=lambda r: r.priority_score, reverse=True)
        if top_n is not None:
            sorted_results = sorted_results[:top_n]
        data = [_result_to_dict(r) for r in sorted_results]
        json.dump(data, sys.stdout, indent=2)
    else:
        _print_report(results, top_n)
