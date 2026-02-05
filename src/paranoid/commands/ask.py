"""Ask command: hybrid graph + RAG over codebase (Phase 5C)."""

from __future__ import annotations

import sys
from pathlib import Path

from paranoid.config import load_config, require_project_root
from paranoid.graph.query import CallerInfo, GraphQueries
from paranoid.llm.ollama import OllamaConnectionError, embed as ollama_embed, summarize as ollama_generate
from paranoid.llm.query_classifier import ClassifiedQuery, QueryType, classify_query
from paranoid.rag.store import VecResult, VectorStore
from paranoid.storage import SQLiteStorage

# Prompt template for RAG: context (retrieved summaries) + user question
ASK_SYSTEM = """You are answering a question about a codebase. Use only the following codebase summaries. If the answer is not in the summaries, say so. Be concise and cite paths when relevant."""

# Prompt for explanation queries (graph context + RAG)
ASK_HYBRID_SYSTEM = """You are answering a question about a codebase. Use the code graph context (callers, callees, definitions) and the codebase summaries below. Combine both to give an accurate answer. Cite file paths and entity names when relevant."""

# Prompt for generation queries (code creation)
ASK_GENERATION_SYSTEM = """You are helping generate or write code based on the codebase. Use the summaries and context below. Produce concrete, runnable code when asked. Cite relevant paths and patterns from the codebase."""


def _build_context(results: list[VecResult]) -> str:
    """Format retrieved VecResults as a single context block."""
    parts = []
    for r in results:
        parts.append(f"--- {r.path} ---\n{r.description}")
    return "\n\n".join(parts)


def _format_usage_answer(entity_name: str, callers: list[CallerInfo]) -> str:
    """Format graph usage result as human-readable answer."""
    if not callers:
        return f"No callers found for '{entity_name}' in the code graph."
    lines = [f"'{entity_name}' is called by:\n"]
    seen: set[tuple[str, str]] = set()
    for c in callers:
        key = (c.qualified_name, c.file_path)
        if key in seen:
            continue
        seen.add(key)
        loc = f" at {c.location}" if c.location else ""
        lines.append(f"  - {c.qualified_name} in {c.file_path}{loc}")
    return "\n".join(lines)


def _format_definition_answer(entities: list) -> str:
    """Format graph definition result as human-readable answer."""
    if not entities:
        return "No definition found in the code graph."
    lines = ["Definitions:\n"]
    for e in entities:
        loc = f"{e.file_path}:{e.lineno}" if e.lineno else e.file_path
        sig = f" {e.signature}" if e.signature else ""
        lines.append(f"  - {e.qualified_name} in {loc}{sig}")
        if e.docstring:
            preview = (e.docstring[:80] + "...") if len(e.docstring) > 80 else e.docstring
            lines.append(f"    {preview}")
    return "\n".join(lines)


def _build_graph_context_for_entity(graph: GraphQueries, entity_name: str) -> str | None:
    """Build graph context string for an entity (callers, callees, inheritance)."""
    entities = graph.find_definition(entity_name)
    if not entities:
        return None
    parts = [f"Code graph for '{entity_name}':\n"]
    for ent in entities[:3]:  # Limit to first 3 matches
        if ent.id is None:
            continue
        callers = graph.get_callers(ent)
        callees = graph.get_callees(ent)
        parts.append(f"  {ent.qualified_name} ({ent.file_path}:{ent.lineno})")
        if callers:
            names = [c.qualified_name for c in callers[:5]]
            if len(callers) > 5:
                names.append(f"...+{len(callers) - 5} more")
            parts.append(f"    Callers: {', '.join(names)}")
        if callees:
            names = [c.target_name for c in callees[:5]]
            if len(callees) > 5:
                names.append(f"...+{len(callees) - 5} more")
            parts.append(f"    Callees: {', '.join(names)}")
        if ent.docstring:
            preview = (ent.docstring[:120] + "...") if len(ent.docstring) > 120 else ent.docstring
            parts.append(f"    Docstring: {preview}")
    return "\n".join(parts) if len(parts) > 1 else None


def _try_graph_usage(
    storage: SQLiteStorage, project_root: Path, entity_name: str
) -> tuple[str | None, list[CallerInfo] | None]:
    """
    Try to answer usage query via graph. Returns (answer_text, callers) or (None, None) if no result.
    """
    graph = GraphQueries(storage, project_root)
    entities = graph.find_definition(entity_name)
    if not entities:
        return None, None
    all_callers: list[CallerInfo] = []
    for ent in entities:
        if ent.id is not None:
            all_callers.extend(graph.get_callers(ent))
    return _format_usage_answer(entity_name, all_callers), all_callers


def _try_graph_definition(
    storage: SQLiteStorage, project_root: Path, entity_name: str
) -> str | None:
    """Try to answer definition query via graph. Returns answer text or None if no result."""
    graph = GraphQueries(storage, project_root)
    entities = graph.find_definition(entity_name)
    if not entities:
        return None
    return _format_definition_answer(entities)


def run(args) -> None:
    """Run the ask command: classify query, route to graph or RAG, combine results."""
    path: Path = getattr(args, "path", Path("."))
    path = path.resolve()
    project_root = require_project_root(path)

    question = getattr(args, "question", None)
    if not question or not question.strip():
        print("Error: provide a question (e.g. paranoid ask \"where is auth handled?\").", file=sys.stderr)
        sys.exit(1)
    question = question.strip()

    force_rag = getattr(args, "force_rag", False)
    config = load_config(project_root)
    classifier_model = getattr(args, "classifier_model", None)
    classified: ClassifiedQuery = classify_query(
        question, config=config, classifier_model=classifier_model
    )
    storage = SQLiteStorage(project_root)
    storage._connect()
    has_graph = storage.has_graph_data()
    summary_count = len(storage.get_all_summaries(scope_path=None))
    storage.close()

    # Try graph-first for usage/definition when graph available and not force_rag
    if not force_rag and has_graph and classified.entity_name:
        if classified.query_type == QueryType.USAGE:
            storage = SQLiteStorage(project_root)
            storage._connect()
            answer, callers = _try_graph_usage(storage, project_root, classified.entity_name)
            storage.close()
            if answer is not None:
                print(answer)
                if getattr(args, "sources", False) and callers:
                    _print_graph_sources(callers)
                return
        elif classified.query_type == QueryType.DEFINITION:
            storage = SQLiteStorage(project_root)
            storage._connect()
            answer = _try_graph_definition(storage, project_root, classified.entity_name)
            storage.close()
            if answer is not None:
                print(answer)
                return

    # RAG path: need summaries, index, model, embedding_model
    model = getattr(args, "model", None) or config.get("default_model")
    embedding_model = getattr(args, "embedding_model", None) or config.get(
        "default_embedding_model"
    )
    vector_k = getattr(args, "vector_k", 20)
    top_k = getattr(args, "top_k", 5)
    type_filter: str | None = None
    if getattr(args, "files_only", False):
        type_filter = "file"
    elif getattr(args, "dirs_only", False):
        type_filter = "directory"
    if not model:
        print("Error: --model is required (or set default_model in config).", file=sys.stderr)
        sys.exit(1)
    if not embedding_model:
        print(
            "Error: --embedding-model is required for RAG (or set default_embedding_model in config).",
            file=sys.stderr,
        )
        sys.exit(1)

    if summary_count == 0:
        print("No summaries found. Run 'paranoid summarize .' first.", file=sys.stderr)
        sys.exit(1)

    vec_store = VectorStore(project_root)
    try:
        vec_store._connect()
        vec_count = vec_store.count()
    finally:
        vec_store.close()

    if vec_count == 0:
        print(
            "Vector index is empty. Run 'paranoid index' to embed summaries for RAG.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        query_embedding = ollama_embed(embedding_model, question)
    except OllamaConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    with VectorStore(project_root) as vec_store:
        results = vec_store.query_similar(
            query_embedding,
            vector_k=vector_k,
            type_filter=type_filter,
            top_k=top_k,
        )

    if not results:
        print("No similar summaries found (dimension mismatch?). Re-run 'paranoid index'.", file=sys.stderr)
        sys.exit(1)

    context = _build_context(results)

    # For explanation queries, prepend graph context (definitions, callers, callees, docstrings) when available
    graph_context_block = ""
    if (
        has_graph
        and classified.entity_name
        and classified.query_type == QueryType.EXPLANATION
    ):
        storage = SQLiteStorage(project_root)
        storage._connect()
        graph = GraphQueries(storage, project_root)
        graph_context_block = _build_graph_context_for_entity(graph, classified.entity_name)
        storage.close()
        if graph_context_block:
            context = f"## Code graph\n{graph_context_block}\n\n## Codebase summaries\n{context}"

    if classified.query_type == QueryType.GENERATION:
        system = ASK_GENERATION_SYSTEM
    elif graph_context_block:
        system = ASK_HYBRID_SYSTEM
    else:
        system = ASK_SYSTEM
    prompt = f"{system}\n\n{context}\n\n## Question\n{question}\n\n## Answer\n"

    try:
        answer, _ = ollama_generate(prompt, model)
    except OllamaConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(answer)

    show_sources = getattr(args, "sources", False)
    if show_sources and results:
        _print_sources(results)


def _print_sources(results: list[VecResult]) -> None:
    """Print retrieved sources (path, type, relevance, preview) for file and directory results."""
    print("\n--- Sources ---")
    for i, r in enumerate(results, 1):
        # L2 distance: lower = more similar; convert to relevance in (0, 1]
        relevance = 1.0 / (1.0 + r.distance) if r.distance is not None else 0.0
        path_label = f"{r.path} ({r.type})" if r.type in ("file", "directory") else r.path
        print(f"{i}. {path_label}")
        print(f"   Relevance: {relevance:.2f}")
        preview = (r.description[:100] + "...") if len(r.description) > 100 else r.description
        print(f"   {preview}")
        print()


def _print_graph_sources(callers: list[CallerInfo]) -> None:
    """Print graph-based sources (callers) in same style as RAG sources."""
    print("\n--- Sources (from code graph) ---")
    seen: set[tuple[str, str]] = set()
    for i, c in enumerate(callers, 1):
        key = (c.qualified_name, c.file_path)
        if key in seen:
            continue
        seen.add(key)
        loc = f" at {c.location}" if c.location else ""
        print(f"{i}. {c.qualified_name} in {c.file_path}{loc}")
        print()
