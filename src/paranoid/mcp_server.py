"""MCP server for Paranoid – exposes tools to AI agents (Cursor, Claude Code, etc.)."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any

try:
    from fastmcp import FastMCP
except ImportError:
    sys.exit(
        "FastMCP is required for the MCP server. Install with: pip install -e \".[mcp]\""
    )

from pathspec import PathSpec

from paranoid.config import load_config, find_project_root
from paranoid.graph.query import CallerInfo, GraphQueries
from paranoid.rag.store import VectorStore
from paranoid.storage import SQLiteStorage, ProjectStats
from paranoid.utils.ignore import build_spec, is_ignored, load_patterns


def _run_cli(command: str, args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """Run paranoid CLI subcommand. Returns (returncode, stdout, stderr)."""
    argv = ["paranoid", command] + [str(a) for a in args]
    script = f"import sys; sys.argv = {repr(argv)}; from paranoid.cli import main; main()"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    return result.returncode, result.stdout or "", result.stderr or ""


def _error_json(error: str, message: str) -> str:
    """Return a JSON object with error structure for agent consumption."""
    return json.dumps({"error": error, "message": message})


def _structured_error(
    error: str,
    message: str,
    remedy: str | None = None,
    next_steps: list[str] | None = None,
) -> str:
    """Return a structured JSON error so the agent can assess readiness and inform the user what to run."""
    d: dict[str, Any] = {"error": error, "message": message}
    if remedy:
        d["remedy"] = remedy
    if next_steps is not None:
        d["next_steps"] = next_steps
    return json.dumps(d)


# In-memory job registry for async summarize/index. Jobs are lost on server restart.
_job_registry: dict[str, dict[str, Any]] = {}
_job_registry_lock = threading.Lock()


def _run_job(job_id: str, command: str, args: list[str], cwd: Path) -> None:
    """Run CLI command in background; update job registry on completion."""
    code, stdout, stderr = _run_cli(command, args, cwd=cwd)
    out = (stdout + "\n" + stderr).strip() if stderr else stdout.strip()
    with _job_registry_lock:
        _job_registry[job_id]["status"] = "completed" if code == 0 else "failed"
        _job_registry[job_id]["returncode"] = code
        _job_registry[job_id]["output"] = out
        if code != 0:
            _job_registry[job_id]["error"] = out


def _format_timestamp(iso_str: str | None) -> str:
    """Return a short human-readable timestamp, or 'never' if None."""
    if not iso_str:
        return "never"
    try:
        return iso_str.replace("T", " ")[:19]
    except Exception:
        return iso_str or "never"


def _stats_to_dict(stats: ProjectStats, total_files: int, total_dirs: int) -> dict:
    """Convert ProjectStats to a JSON-serializable dict."""
    summarized_files = stats.count_by_type.get("file", 0)
    summarized_dirs = stats.count_by_type.get("directory", 0)
    summarized_total = summarized_files + summarized_dirs
    total_items = total_files + total_dirs
    coverage_pct = (100.0 * summarized_total / total_items) if total_items > 0 else 0.0

    return {
        "by_type": {
            "files": summarized_files,
            "directories": summarized_dirs,
            "total": summarized_total,
        },
        "coverage": {
            "summarized": summarized_total,
            "total_items": total_items,
            "percentage": round(coverage_pct, 1),
        },
        "last_updated": _format_timestamp(stats.last_updated_at),
        "by_language": dict(stats.language_breakdown or []),
        "model_usage": dict(stats.model_breakdown or []),
    }


def _count_summarizable(
    root_path: Path,
    project_root: Path,
    spec: PathSpec,
) -> tuple[int, int]:
    """Count files and dirs that would be summarized (not ignored). Returns (file_count, dir_count)."""
    root_path = root_path.resolve()
    project_root = project_root.resolve()
    file_count = 0
    dir_count = 0

    if root_path.is_file():
        if is_ignored(root_path, project_root, spec):
            return (0, 0)
        return (1, 0)

    if not root_path.is_dir():
        return (0, 0)

    def recurse(current: Path) -> None:
        nonlocal file_count, dir_count
        try:
            entries = list(current.iterdir())
        except OSError:
            return
        for entry in sorted(entries, key=lambda p: p.name):
            if entry.is_file():
                if is_ignored(entry, project_root, spec):
                    continue
                file_count += 1
            else:
                if is_ignored(entry, project_root, spec):
                    continue
                recurse(entry)
                dir_count += 1

    recurse(root_path)
    if not is_ignored(root_path, project_root, spec):
        dir_count += 1

    return (file_count, dir_count)


# FastMCP server (stdio transport by default for Cursor and other MCP clients)
mcp = FastMCP(
    "Paranoid",
    description="Local-only codebase summarization and analysis via Ollama. Ask questions, get stats, check docs. All tools require project_path (absolute or relative); agent passes explicitly.",
)


@mcp.tool
def paranoid_stats(project_path: str) -> str:
    """
    Get summary statistics for a Paranoid project: coverage, language breakdown, last update, model usage.

    Args:
        project_path: Absolute or relative path to the project root (must contain .paranoid-coder).

    Returns:
        JSON object with stats, or an error message if project is not initialized.
    """
    path = Path(project_path).resolve()
    root = find_project_root(path)
    if root is None:
        return _structured_error(
            "Project not initialized",
            "No paranoid project found. Run paranoid_init to create .paranoid-coder and the database.",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )

    config = load_config(root)
    patterns_with_source = load_patterns(root, config)
    patterns = [p for p, _ in patterns_with_source]
    spec = build_spec(patterns)

    scope_path = path.as_posix() if path.is_dir() else path.parent.as_posix()
    total_files, total_dirs = _count_summarizable(path, root, spec)

    storage = SQLiteStorage(root)
    with storage:
        stats = storage.get_stats(scope_path=scope_path)
        return json.dumps(_stats_to_dict(stats, total_files, total_dirs), indent=2)


@mcp.tool
def paranoid_readiness(project_path: str) -> str:
    """
    Assess project readiness: check if initialized, has code graph, summaries, and RAG index.

    Use this to inform the user what to run (init, analyze, summarize, index) before other tools.
    Returns structured JSON with boolean flags and a next_steps list of recommended tools.

    Args:
        project_path: Absolute or relative path to the project root.

    Returns:
        JSON with: initialized, has_graph, has_summaries, summary_count, has_index, indexed_summaries,
        indexed_entities, next_steps, ready_for_ask, ready_for_doctor, ready_for_find_usages.
    """
    path = Path(project_path).resolve()
    root = find_project_root(path)
    if root is None:
        return _structured_error(
            "Project not initialized",
            "No paranoid project found. Run paranoid_init to create .paranoid-coder and the database.",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )
    storage = SQLiteStorage(root)
    with storage:
        has_graph = storage.has_graph_data()
        summaries = storage.get_all_summaries(scope_path=None)
        summary_count = len(summaries)
        has_summaries = summary_count > 0

    vec_store = VectorStore(root)
    try:
        vec_store._connect()
        indexed_summaries = vec_store.count()
        indexed_entities = vec_store.entity_count()
        vec_store.close()
    except Exception:
        indexed_summaries = 0
        indexed_entities = 0
    has_index = indexed_summaries > 0 or indexed_entities > 0

    next_steps: list[str] = []
    if not has_graph:
        next_steps.append("paranoid_analyze")
    if not has_summaries:
        next_steps.append("paranoid_summarize")
    if has_summaries and not has_index:
        next_steps.append("paranoid_index")

    return json.dumps({
        "project_path": root.as_posix(),
        "initialized": True,
        "has_graph": has_graph,
        "has_summaries": has_summaries,
        "summary_count": summary_count,
        "has_index": has_index,
        "indexed_summaries": indexed_summaries,
        "indexed_entities": indexed_entities,
        "next_steps": next_steps,
        "ready_for_ask": has_summaries and has_index,
        "ready_for_doctor": has_graph,
        "ready_for_find_usages": has_graph,
        "ready_for_find_definition": has_graph,
    }, indent=2)


@mcp.tool
def paranoid_init(project_path: str) -> str:
    """
    Initialize a Paranoid project at the given path. Creates .paranoid-coder and the database.
    Idempotent: safe to run if already initialized.

    Args:
        project_path: Absolute or relative path to the directory to initialize.

    Returns:
        Success message, or JSON error if path is invalid.
    """
    path = Path(project_path).resolve()
    if not path.exists():
        return _structured_error(
            "Path does not exist",
            f"Path {path.as_posix()} does not exist.",
            remedy="paranoid_init",
            next_steps=[],
        )
    if path.is_file():
        path = path.parent
    code, stdout, stderr = _run_cli("init", [path.as_posix()])
    out = (stdout + "\n" + stderr).strip() if stderr else stdout.strip()
    if code != 0:
        return _structured_error(
            "Init failed",
            out or "Unknown error",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )
    return json.dumps({
        "status": "initialized",
        "project_root": path.as_posix(),
        "message": out,
    })


@mcp.tool
def paranoid_ask(
    project_path: str,
    question: str,
    include_sources: bool = False,
) -> str:
    """
    Ask a question about the codebase. Uses graph (usage/definition), RAG (summaries + entities), and LLM synthesis.

    Args:
        project_path: Absolute or relative path to the project root (must contain .paranoid-coder).
        question: Natural language question (e.g. "where is authentication handled?").
        include_sources: If True, include source citations (file paths, relevance) in the response.

    Returns:
        The answer text, with optional sources. JSON error if project not initialized, no summaries, or no index.
    """
    path = Path(project_path).resolve()
    root = find_project_root(path)
    if root is None:
        return _structured_error(
            "Project not initialized",
            "No paranoid project found. Run paranoid_init first.",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )
    args = [question.strip(), path.as_posix()]
    if include_sources:
        args.append("--sources")
    code, stdout, stderr = _run_cli("ask", args, cwd=root)
    if code != 0:
        err = (stderr or stdout).strip()
        return _structured_error(
            "Ask failed",
            err,
            remedy="paranoid_readiness",
            next_steps=["paranoid_readiness"],
        )
    return stdout.strip() or stderr.strip()


@mcp.tool
def paranoid_doctor(
    project_path: str,
    top: int | None = None,
    format: str = "json",
) -> str:
    """
    Get a documentation quality report: missing docstrings, examples, type hints, priority scores.

    Args:
        project_path: Absolute or relative path to the project root (must contain .paranoid-coder).
        top: If set, show only top N items by priority.
        format: Output format: "json" or "text".

    Returns:
        Report as JSON (default) or text. JSON error if project not initialized or no code graph.
    """
    path = Path(project_path).resolve()
    root = find_project_root(path)
    if root is None:
        return _structured_error(
            "Project not initialized",
            "No paranoid project found. Run paranoid_init first.",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )
    args = [path.as_posix(), "--format", format]
    if top is not None:
        args.extend(["--top", str(top)])
    code, stdout, stderr = _run_cli("doctor", args, cwd=root)
    if code != 0:
        err = (stderr or stdout).strip()
        return _structured_error(
            "Doctor failed",
            err,
            remedy="paranoid_analyze",
            next_steps=["paranoid_analyze", "paranoid_readiness"],
        )
    if format == "json":
        return stdout.strip()
    return (stdout + "\n" + stderr).strip() if stderr else stdout.strip()


@mcp.tool
def paranoid_analyze(project_path: str, force: bool = False) -> str:
    """
    Extract the code graph from the project (entities, relationships). Fast, no LLM.

    Args:
        project_path: Absolute or relative path to the project root (must contain .paranoid-coder).
        force: If True, re-analyze all files (default: incremental, skip unchanged).

    Returns:
        Summary of entities and relationships extracted. JSON error if project not initialized.
    """
    path = Path(project_path).resolve()
    root = find_project_root(path)
    if root is None:
        return _structured_error(
            "Project not initialized",
            "No paranoid project found. Run paranoid_init first.",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )
    args = [path.as_posix()]
    if force:
        args.append("--force")
    code, stdout, stderr = _run_cli("analyze", args, cwd=root)
    if code != 0:
        err = (stderr or stdout).strip()
        return _structured_error(
            "Analyze failed",
            err,
            remedy="paranoid_readiness",
            next_steps=["paranoid_readiness"],
        )
    out = (stdout + "\n" + stderr).strip() if stderr else stdout.strip()
    return json.dumps({"status": "ok", "output": out})


@mcp.tool
def paranoid_find_usages(project_path: str, entity_name: str) -> str:
    """
    Find where an entity (function, method, class) is called. Graph-only, instant.

    Requires paranoid_analyze to have been run. Use qualified names (e.g. "User.login", "greet").

    Args:
        project_path: Absolute or relative path to the project root (must contain .paranoid-coder).
        entity_name: Entity to find usages for (e.g. "greet", "MyClass.my_method").

    Returns:
        JSON with callers: list of {qualified_name, file_path, location}. Empty if none or no graph.
    """
    path = Path(project_path).resolve()
    root = find_project_root(path)
    if root is None:
        return _structured_error(
            "Project not initialized",
            "No paranoid project found. Run paranoid_init first.",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )
    storage = SQLiteStorage(root)
    with storage:
        if not storage.has_graph_data():
            return _structured_error(
                "No code graph",
                "Run paranoid_analyze first to extract the code graph.",
                remedy="paranoid_analyze",
                next_steps=["paranoid_analyze"],
            )
        graph = GraphQueries(storage, root)
        entities = graph.find_definition(entity_name)
        if not entities:
            return json.dumps({
                "entity_name": entity_name,
                "callers": [],
                "message": f"No definition found for '{entity_name}' in the code graph.",
            })
        all_callers: list[CallerInfo] = []
        for ent in entities:
            if ent.id is not None:
                all_callers.extend(graph.get_callers(ent))
        seen: set[tuple[str, str]] = set()
        callers_list: list[dict[str, str]] = []
        for c in all_callers:
            key = (c.qualified_name, c.file_path)
            if key in seen:
                continue
            seen.add(key)
            callers_list.append({
                "qualified_name": c.qualified_name,
                "file_path": c.file_path,
                "location": c.location or "",
            })
        return json.dumps({
            "entity_name": entity_name,
            "callers": callers_list,
            "count": len(callers_list),
        }, indent=2)


@mcp.tool
def paranoid_find_definition(project_path: str, entity_name: str) -> str:
    """
    Find where an entity (function, method, class) is defined. Graph-only, instant.

    Requires paranoid_analyze to have been run. Use qualified names (e.g. "User.login", "greet").

    Args:
        project_path: Absolute or relative path to the project root (must contain .paranoid-coder).
        entity_name: Entity to find (e.g. "greet", "MyClass.my_method").

    Returns:
        JSON with definitions: list of {qualified_name, file_path, lineno, signature, docstring_preview}.
    """
    path = Path(project_path).resolve()
    root = find_project_root(path)
    if root is None:
        return _structured_error(
            "Project not initialized",
            "No paranoid project found. Run paranoid_init first.",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )
    storage = SQLiteStorage(root)
    with storage:
        if not storage.has_graph_data():
            return _structured_error(
                "No code graph",
                "Run paranoid_analyze first to extract the code graph.",
                remedy="paranoid_analyze",
                next_steps=["paranoid_analyze"],
            )
        graph = GraphQueries(storage, root)
        entities = graph.find_definition(entity_name)
        if not entities:
            return json.dumps({
                "entity_name": entity_name,
                "definitions": [],
                "message": f"No definition found for '{entity_name}' in the code graph.",
            })
        defs_list: list[dict[str, Any]] = []
        for e in entities:
            loc = f"{e.file_path}:{e.lineno}" if e.lineno else e.file_path
            defs_list.append({
                "qualified_name": e.qualified_name,
                "file_path": e.file_path,
                "lineno": e.lineno,
                "location": loc,
                "signature": e.signature or "",
                "docstring_preview": (e.docstring[:120] + "...") if e.docstring and len(e.docstring) > 120 else (e.docstring or ""),
            })
        return json.dumps({
            "entity_name": entity_name,
            "definitions": defs_list,
            "count": len(defs_list),
        }, indent=2)


@mcp.tool
def paranoid_summarize(
    project_path: str,
    model: str | None = None,
    force: bool = False,
) -> str:
    """
    Generate summaries for files and directories. Runs asynchronously; returns immediately with a job ID.

    Long-running (minutes on large projects). Poll paranoid_job_status(job_id) to check completion,
    or paranoid_stats(project_path) to detect progress (summary count, last_updated change).

    Polling strategy: Call paranoid_job_status every 5–10 seconds to check status. Alternatively,
    call paranoid_stats periodically; when summary count or last_updated changes, work is progressing.
    For very long runs (hours), consider running `paranoid summarize` via CLI directly.

    Args:
        project_path: Absolute or relative path to the project root (must contain .paranoid-coder).
        model: Ollama model name (e.g. qwen2.5-coder:7b). Uses config default if not set.
        force: If True, re-summarize even when content is unchanged.

    Returns:
        JSON with job_id and polling instructions. Use paranoid_job_status(job_id) to check completion.
    """
    path = Path(project_path).resolve()
    root = find_project_root(path)
    if root is None:
        return _structured_error(
            "Project not initialized",
            "No paranoid project found. Run paranoid_init first.",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )
    args = [path.as_posix()]
    if model:
        args.extend(["--model", model])
    if force:
        args.append("--force")

    job_id = str(uuid.uuid4())
    with _job_registry_lock:
        _job_registry[job_id] = {
            "status": "running",
            "command": "summarize",
            "project_path": root.as_posix(),
            "returncode": None,
            "output": None,
            "error": None,
        }
    thread = threading.Thread(target=_run_job, args=(job_id, "summarize", args, root))
    thread.daemon = True
    thread.start()

    return json.dumps({
        "job_id": job_id,
        "status": "running",
        "command": "summarize",
        "project_path": root.as_posix(),
        "polling": "Call paranoid_job_status(job_id) to check completion, or paranoid_stats(project_path) to detect progress.",
    }, indent=2)


@mcp.tool
def paranoid_index(project_path: str, full: bool = False) -> str:
    """
    Build or refresh the RAG index (embed summaries and entities for semantic search).
    Runs asynchronously; returns immediately with a job ID.

    Long-running on large projects. Poll paranoid_job_status(job_id) to check completion,
    or paranoid_stats(project_path) to detect progress (last_updated changes when indexing completes).

    Polling strategy: Call paranoid_job_status every 5–10 seconds to check status. Alternatively,
    call paranoid_stats periodically; when last_updated changes, indexing may have progressed.
    For very long runs, consider running `paranoid index` via CLI directly.

    Args:
        project_path: Absolute or relative path to the project root (must contain .paranoid-coder).
        full: If True, full reindex from scratch (default: incremental).

    Returns:
        JSON with job_id and polling instructions. Use paranoid_job_status(job_id) to check completion.
    """
    path = Path(project_path).resolve()
    root = find_project_root(path)
    if root is None:
        return _structured_error(
            "Project not initialized",
            "No paranoid project found. Run paranoid_init first.",
            remedy="paranoid_init",
            next_steps=["paranoid_init"],
        )
    args = [path.as_posix()]
    if full:
        args.append("--full")

    job_id = str(uuid.uuid4())
    with _job_registry_lock:
        _job_registry[job_id] = {
            "status": "running",
            "command": "index",
            "project_path": root.as_posix(),
            "returncode": None,
            "output": None,
            "error": None,
        }
    thread = threading.Thread(target=_run_job, args=(job_id, "index", args, root))
    thread.daemon = True
    thread.start()

    return json.dumps({
        "job_id": job_id,
        "status": "running",
        "command": "index",
        "project_path": root.as_posix(),
        "polling": "Call paranoid_job_status(job_id) to check completion, or paranoid_stats(project_path) to detect progress.",
    }, indent=2)


@mcp.tool
def paranoid_job_status(job_id: str, include_stats: bool = True) -> str:
    """
    Check the status of an async job (paranoid_summarize or paranoid_index).

    Use this to poll for completion after starting summarize or index. Alternatively,
    poll paranoid_stats(project_path) to detect progress (summary count, last_updated).

    Polling strategy: Call every 5–10 seconds. When status is "completed" or "failed",
    the job is done. For very long runs (hours), the user may need to run the CLI directly.

    Args:
        job_id: The job ID returned by paranoid_summarize or paranoid_index.
        include_stats: If True and job exists, include current project stats (summary count,
            last_updated) so the agent can see progress without a separate paranoid_stats call.

    Returns:
        JSON with status (running/completed/failed), output, and optionally current stats.
    """
    with _job_registry_lock:
        job = _job_registry.get(job_id)
    if not job:
        return _error_json("Job not found", f"Unknown job_id: {job_id}. Jobs are in-memory; server restart clears them.")

    result: dict[str, Any] = {
        "job_id": job_id,
        "status": job["status"],
        "command": job["command"],
        "project_path": job["project_path"],
    }
    if job["status"] in ("completed", "failed"):
        result["output"] = job.get("output") or job.get("error")
        result["returncode"] = job.get("returncode")
    if job["status"] == "failed":
        result["error"] = job.get("error", "Command failed")

    if include_stats and job.get("project_path"):
        root = Path(job["project_path"])
        if root.exists() and find_project_root(root) is not None:
            config = load_config(root)
            patterns_with_source = load_patterns(root, config)
            patterns = [p for p, _ in patterns_with_source]
            spec = build_spec(patterns)
            scope = root.as_posix()
            total_files, total_dirs = _count_summarizable(root, root, spec)
            storage = SQLiteStorage(root)
            with storage:
                stats = storage.get_stats(scope_path=scope)
            result["stats"] = _stats_to_dict(stats, total_files, total_dirs)

    return json.dumps(result, indent=2)


def main() -> None:
    """Run the MCP server with stdio transport (for Cursor and other MCP clients)."""
    mcp.run()
