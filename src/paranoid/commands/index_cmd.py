"""Index command: embed summaries and entities for RAG (full or incremental)."""

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


def _entity_text_for_embedding(qualified_name: str, signature: str | None, docstring: str | None) -> str:
    """Build text to embed for an entity: qualified_name, signature, docstring."""
    parts = [qualified_name]
    if signature:
        parts.append(signature)
    if docstring:
        parts.append(docstring)
    return "\n".join(parts)


def run(args) -> None:
    """Run the index command: embed summaries and/or entities for RAG."""
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

    if index_files:
        print(
            "File-content indexing is not yet implemented; only summaries and entities will be indexed.",
            file=sys.stderr,
        )

    if not index_summaries and not index_entities:
        print(
            "Nothing to index. Use --summaries and/or --entities (or --summaries-only / --entities-only).",
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
    summaries = storage.get_all_summaries(scope_path=None) if index_summaries else []
    has_graph = storage.has_graph_data()
    entities_for_index = (
        storage.get_entities_for_indexing(scope_path=None) if index_entities and has_graph else []
    )
    storage.close()

    if index_summaries and not summaries:
        print("No summaries found. Run 'paranoid summarize .' first.", file=sys.stderr)
        if not index_entities:
            sys.exit(0)
    if index_entities and not has_graph:
        print(
            "No code graph. Run 'paranoid analyze .' first to index entities.",
            file=sys.stderr,
        )
        if not index_summaries:
            sys.exit(0)
        entities_for_index = []

    vec_store = VectorStore(project_root)
    try:
        vec_store._connect()
        indexed = vec_store.get_indexed_paths()
        indexed_entities = vec_store.get_indexed_entities()
        stored_dim = vec_store.embed_dim()
    finally:
        vec_store.close()

    # Embedding dimension: use from summaries if available, else we'll get it from first batch
    summary_count = 0
    entity_count = 0

    if index_summaries and summaries:
        do_full = full_reindex or not indexed or stored_dim is None
        if do_full:
            _run_full_index(project_root, summaries, embedding_model, vec_store)
        else:
            _run_incremental_index(
                project_root, summaries, indexed, embedding_model, vec_store
            )
        vec_store = VectorStore(project_root)
        vec_store._connect()
        summary_count = vec_store.count()
        stored_dim = vec_store.embed_dim()
        vec_store.close()

    if index_entities and entities_for_index:
        do_full_entities = full_reindex or not indexed_entities or stored_dim is None
        if do_full_entities:
            _run_full_entity_index(
                project_root, entities_for_index, embedding_model, vec_store, stored_dim
            )
        else:
            _run_incremental_entity_index(
                project_root,
                entities_for_index,
                indexed_entities,
                embedding_model,
                vec_store,
                stored_dim,
            )
        vec_store = VectorStore(project_root)
        vec_store._connect()
        entity_count = vec_store.entity_count()
        vec_store.close()

    # Report
    parts = []
    if index_summaries:
        parts.append(f"{summary_count} summaries")
    if index_entities:
        parts.append(f"{entity_count} entities")
    if parts:
        print(f"Indexed {', '.join(parts)}.", file=sys.stderr)


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


def _run_full_entity_index(
    project_root: Path,
    entities_for_index: list[tuple],
    embedding_model: str,
    vec_store: VectorStore,
    stored_dim: int | None,
) -> None:
    """Embed all entities and replace vec_entities table."""
    texts = [
        _entity_text_for_embedding(e.qualified_name, e.signature, e.docstring)
        for e, _ in entities_for_index
    ]
    if not texts:
        return
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
    if stored_dim is not None and dim != stored_dim:
        print(
            f"Warning: Entity embedding dim ({dim}) differs from summary dim ({stored_dim}). "
            "Using same embedding model for both is recommended.",
            file=sys.stderr,
        )
    vec_store._connect()
    vec_store.clear_entities()
    vec_store.ensure_entities_table(dim)
    rows = []
    for j, (entity, updated_at) in enumerate(entities_for_index):
        desc = _entity_text_for_embedding(
            entity.qualified_name, entity.signature, entity.docstring
        )
        rows.append(
            (
                entity.id,
                entity.file_path,
                entity.qualified_name,
                entity.lineno or 0,
                entity.end_lineno or entity.lineno or 0,
                updated_at,
                desc,
                entity.signature,
                all_embeddings[j],
            )
        )
    vec_store.insert_entities_batch(rows)
    vec_store.close()


def _run_incremental_entity_index(
    project_root: Path,
    entities_for_index: list[tuple],
    indexed_entities: dict[int, str],
    embedding_model: str,
    vec_store: VectorStore,
    stored_dim: int | None,
) -> None:
    """Embed only new or changed entities and remove stale ones."""
    current_ids = {e.id for e, _ in entities_for_index if e.id is not None}
    # Remove embeddings for entities no longer in code_entities
    for eid in list(indexed_entities):
        if eid not in current_ids:
            vec_store._connect()
            vec_store.delete_entity_by_id(eid)
            vec_store.close()

    needs_embedding = [
        (e, up)
        for e, up in entities_for_index
        if e.id is not None
        and (e.id not in indexed_entities or up > indexed_entities[e.id])
    ]
    if not needs_embedding:
        return

    texts = [
        _entity_text_for_embedding(e.qualified_name, e.signature, e.docstring)
        for e, _ in needs_embedding
    ]
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
    if stored_dim is not None and dim != stored_dim:
        print(
            f"Warning: Entity embedding dim ({dim}) differs from summary dim ({stored_dim}).",
            file=sys.stderr,
        )
    vec_store._connect()
    vec_store.ensure_entities_table(dim)
    for j, (entity, updated_at) in enumerate(needs_embedding):
        vec_store.delete_entity_by_id(entity.id)
        desc = _entity_text_for_embedding(
            entity.qualified_name, entity.signature, entity.docstring
        )
        vec_store.insert_entity(
            entity.id,
            entity.file_path,
            entity.qualified_name,
            entity.lineno or 0,
            entity.end_lineno or entity.lineno or 0,
            updated_at,
            desc,
            entity.signature,
            all_embeddings[j],
        )
    vec_store.close()
