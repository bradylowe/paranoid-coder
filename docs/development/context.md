# Paranoid — Development Context

A short, condensed view of what we're building and why. For current tasks see **[todo.md](todo.md)**. For full architecture, schema, and roadmap see **[project_plan.md](project_plan.md)**.

---

## What Paranoid Is

- **Paranoid** is a **local-only** codebase summarization and analysis tool. It helps developers understand and navigate projects by generating hierarchical summaries with a local LLM (Ollama). No code or summaries leave the user's machine.
- **This repo** is the **tool**. It is installed once (e.g. `pip install -e .`) and used to work on **other** codebases. Target projects are arbitrary directories the user wants to summarize—e.g. `my-project`, `other-repo`.
- **Why:** Privacy-first alternative to cloud code analysis; fast incremental updates via content hashing; each project stays self-contained.

---

## What We're Building

- **CLI** (`paranoid`): `init`, `summarize`, `view`, `stats`, `config`, `clean`, `export`, `ask`, and (Phase 5A) `index`, `chat`. Paths are resolved to absolute; storage lives in the target project. **`paranoid index`** (Phase 5A) indexes summaries, code entities, and/or file contents for RAG (default: all; use `--summaries-only`, `--entities-only`, `--files-only`, or `--no-files` etc. to scope).
- **Init-only creation:** The **`.paranoid-coder/`** directory and database are created **only** by `paranoid init`. All other commands look for an existing `.paranoid-coder` by walking upward from the given path; if none is found, they print an error and ask the user to run `paranoid init` first.
- **Storage:** Each target project has its own **`.paranoid-coder/`** directory with a SQLite database (`summaries.db`). Summaries are keyed by **normalized full path**; hierarchy is implicit (prefix match). Optional project overrides in `.paranoid-coder/config.json`.
- **Summarization:** Bottom-up tree walk; content hash (SHA-256) and tree hash for change detection; only changed or new items go to Ollama; `.paranoidignore` and `.gitignore` (and built-ins) respected.
- **Viewer:** Desktop GUI (PyQt6) to explore the tree and read summaries; reads from the same `.paranoid-coder/summaries.db`.

---

## Key Design Choices

| Topic | Decision |
|-------|----------|
| Creating `.paranoid-coder` | **Init only:** `paranoid init` is the only way to create the directory and DB; other commands require an existing project. |
| Finding project root | Other commands walk upward from the given path to find a directory containing `.paranoid-coder`; if not found, error and exit. |
| Storage location | **Distributed:** each target has its own `.paranoid-coder/` (not a central ~/.paranoid-coder). |
| Storage key | Normalized **absolute path** per file/directory. No separate "project" table. |
| Hierarchy | Implicit: "children of X" = entries whose path is under X (prefix + one segment for direct children). |
| Moving a project | Stored paths break; re-summarize or a future `remap` command. |
| RAG (future) | Primary store remains SQLite in the project; separate local vector index for retrieval; keep in sync. Phase 5A adds **code entity indexing** (classes, functions, methods) so RAG can answer "where is User.login?" and similar granular questions. |

---

## Current Focus

**Phases 1–4 are complete.** Init, summarize, view, stats, config, clean, export, prompts, and RAG (`paranoid ask`) work; the viewer has tree, detail panel, search, and context menu. **Phase 5A (Code-Aware RAG)** is the next priority: code entity extraction (Python AST), **`paranoid index`** (summaries / entities / file contents; `--summaries-only`, `--entities-only`, `--files-only`, single-file support, `--full`), enhanced `ask`, and interactive `paranoid chat` with `/snippet` and `/related`. See **[todo.md](todo.md)**, **[project_plan.md](project_plan.md)**, and **[indexing_implementation.md](indexing_implementation.md)** for the roadmap and indexing plan.

**Testing:** Unit tests (storage, hashing, ignore) and integration tests (init, summarize with mocked LLM, export) live under `tests/`; see **[tests/README.md](../../tests/README.md)** for how to run and what’s covered.

---

*Keep this doc in sync with the project plan as we implement.*
