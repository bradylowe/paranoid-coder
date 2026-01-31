"""Index command: embed summaries and populate the vector store for RAG (full or incremental)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from paranoid.config import load_config, require_project_root
from paranoid.llm.ollama import OllamaConnectionError, embed as ollama_embed
from paranoid.rag.store import VectorStore
from paranoid.storage import SQLiteStorage

logger = logging.getLogger(__name__)

# Batch size for embedding requests (Ollama accepts list of inputs)
EMBED_BATCH_SIZE = 32


# Disclaimer: only summaries indexing is implemented; entities and file content are planned (Phase 5A).
INDEX_IMPLEMENTATION_NOTE = (
    "Note: Only summaries indexing is currently implemented. "
    "Entity and file-content indexing are planned (Phase 5A)."
)


def run(args) -> None:
    """Run the index command: embed summaries and/or (when implemented) entities and file contents for RAG."""
    # Resolve --*-only flags into what to index
    summaries_only = getattr(args, "summaries_only", False)
    entities_only = getattr(args, "entities_only", False)
    files_only = getattr(args, "files_only", False)
    if summaries_only:
        index_summaries, index_entities, index_files = True, False, False
    elif entities_only:
        index_summaries, index_entities, index_files = False, True, False
    elif files_only:
        index_summaries, index_entities, index_files = False, False, True
    else:
        index_summaries = getattr(args, "index_summaries", True)
        index_entities = getattr(args, "index_entities", True)
        index_files = getattr(args, "index_files", True)

    # Only summaries indexing is implemented
    print(INDEX_IMPLEMENTATION_NOTE, file=sys.stderr)
    if index_entities or index_files:
        print(
            "Entity and file-content indexing are not yet implemented; only summaries will be indexed when requested.",
            file=sys.stderr,
        )
    if not index_summaries:
        print(
            "Only summaries indexing is available. Nothing to do for the requested index types.",
            file=sys.stderr,
        )
        return

    config = load_config(None)
    embedding_model = getattr(args, "embedding_model", None) or config.get(
        "default_embedding_model"
    )
    if not embedding_model:
        print(
            "Error: --embedding-model is required (or set default_embedding_model in config).",
            file=sys.stderr,
        )
        sys.exit(1)

    path: Path = getattr(args, "path", Path("."))
    path = path.resolve()
    project_root = require_project_root(path)
    full_reindex = getattr(args, "full", False)

    config = load_config(project_root)
    storage = SQLiteStorage(project_root)
    storage._connect()
    summaries = storage.get_all_summaries(scope_path=None)
    storage.close()

    if not summaries:
        print("No summaries found. Run 'paranoid summarize .' first.", file=sys.stderr)
        sys.exit(0)

    vec_store = VectorStore(project_root)
    try:
        vec_store._connect()
        indexed = vec_store.get_indexed_paths()
        stored_dim = vec_store.embed_dim()
    finally:
        vec_store.close()

    # Decide: full reindex (--full, or table missing/dim unknown) vs incremental
    do_full = full_reindex or not indexed or stored_dim is None
    if do_full:
        _run_full_index(project_root, summaries, embedding_model, vec_store)
    else:
        _run_incremental_index(
            project_root, summaries, indexed, embedding_model, vec_store
        )
    vec_store = VectorStore(project_root)
    try:
        vec_store._connect()
        count = vec_store.count()
    finally:
        vec_store.close()
    print(f"Indexed {count} summaries.", file=sys.stderr)


def _run_full_index(
    project_root: Path,
    summaries: list,
    embedding_model: str,
    vec_store: VectorStore,
) -> None:
    """Embed all summaries and replace the vector table (path + description per row)."""
    # Text to embed: path + description for better retrieval
    texts = [f"{s.path}\n{s.description}" for s in summaries]
    try:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            batch_embeddings = ollama_embed(embedding_model, batch)
            all_embeddings.extend(batch_embeddings)
    except OllamaConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    dim = len(all_embeddings[0])
    vec_store._connect()
    vec_store.clear()
    vec_store.ensure_table(dim)
    rows = [
        (s.path, s.type, s.updated_at, s.description, all_embeddings[j])
        for j, s in enumerate(summaries)
    ]
    vec_store.insert_batch(rows)
    vec_store.close()


def _run_incremental_index(
    project_root: Path,
    summaries: list,
    indexed: dict[str, str],
    embedding_model: str,
    vec_store: VectorStore,
) -> None:
    """Embed only new or changed summaries (updated_at > indexed) and remove stale paths."""
    summary_paths = {s.path for s in summaries}
    # Remove embeddings for paths no longer in summaries
    for path in list(indexed):
        if path not in summary_paths:
            vec_store._connect()
            vec_store.delete_by_path(path)
            vec_store.close()

    # Find summaries that need embedding: not indexed or summary.updated_at > indexed[path]
    needs_embedding = [
        s
        for s in summaries
        if s.path not in indexed or s.updated_at > indexed[s.path]
    ]
    if not needs_embedding:
        return

    texts = [f"{s.path}\n{s.description}" for s in needs_embedding]
    try:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[i : i + EMBED_BATCH_SIZE]
            batch_embeddings = ollama_embed(embedding_model, batch)
            all_embeddings.extend(batch_embeddings)
    except OllamaConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    vec_store._connect()
    dim = len(all_embeddings[0])
    vec_store.ensure_table(dim)
    for j, s in enumerate(needs_embedding):
        vec_store.delete_by_path(s.path)
        vec_store.insert(
            s.path, s.type, s.updated_at, s.description, all_embeddings[j]
        )
    vec_store.close()
