"""Ask command: RAG over codebase summaries (embed question, retrieve, generate answer)."""

from __future__ import annotations

import sys
from pathlib import Path

from paranoid.config import load_config, require_project_root
from paranoid.llm.ollama import OllamaConnectionError, embed as ollama_embed, summarize as ollama_generate
from paranoid.rag.store import VecResult, VectorStore
from paranoid.storage import SQLiteStorage

# Prompt template for RAG: context (retrieved summaries) + user question
ASK_SYSTEM = """You are answering a question about a codebase. Use only the following codebase summaries. If the answer is not in the summaries, say so. Be concise and cite paths when relevant."""


def _build_context(results: list[VecResult]) -> str:
    """Format retrieved VecResults as a single context block."""
    parts = []
    for r in results:
        parts.append(f"--- {r.path} ---\n{r.description}")
    return "\n\n".join(parts)


def run(args) -> None:
    """Run the ask command: embed question, retrieve top-k, generate answer."""
    config = load_config(None)
    path: Path = getattr(args, "path", Path("."))
    path = path.resolve()
    project_root = require_project_root(path)

    question = getattr(args, "question", None)
    if not question or not question.strip():
        print("Error: provide a question (e.g. paranoid ask \"where is auth handled?\").", file=sys.stderr)
        sys.exit(1)
    question = question.strip()

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

    config = load_config(project_root)
    storage = SQLiteStorage(project_root)
    storage._connect()
    summary_count = len(storage.get_all_summaries(scope_path=None))
    storage.close()

    if summary_count == 0:
        print("No summaries found. Run 'paranoid summarize .' first.", file=sys.stderr)
        sys.exit(0)

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
        sys.exit(0)

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
        sys.exit(0)

    context = _build_context(results)
    prompt = f"{ASK_SYSTEM}\n\n## Codebase summaries\n\n{context}\n\n## Question\n{question}\n\n## Answer\n"

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
