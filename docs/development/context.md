# Paranoid — Development Context

A short, condensed view of what we're building and why. For current tasks see **[todo.md](todo.md)**. For full architecture, schema, and roadmap see **[project_plan.md](project_plan.md)**.

---

## What Paranoid Is

- **Paranoid** is a **local-only** codebase summarization and analysis tool. It helps developers understand and navigate projects by generating hierarchical summaries with a local LLM (Ollama). No code or summaries leave the user's machine.
- **This repo** is the **tool**. It is installed once (e.g. `pip install -e .`) and used to work on **other** codebases. Target projects are arbitrary directories the user wants to summarize—e.g. `my-project`, `other-repo`.
- **Why:** Privacy-first alternative to cloud code analysis; fast incremental updates via content hashing; each project stays self-contained.

---

## What We're Building

- **CLI** (`paranoid`): `init`, `summarize`, `view`, `stats`, `config`, `clean`, `export`. Paths are resolved to absolute; storage lives in the target project.
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
| RAG (future) | Primary store remains SQLite in the project; separate local vector index for retrieval; keep in sync. |

---

## Current Focus

**Phase 1 (MVP) and Phase 2 (viewer & UX) are complete.** Init, summarize, view, stats, and export all work; the viewer has tree, detail panel, search, and context menu (refresh, re-summarize, copy path). **Phase 3** is current: clean command, config command, viewer enhancements (show/hide ignored, highlight stale, refresh/re-summarize), and user documentation. See **[todo.md](todo.md)** for the Phase 3 checklist. The project plan describes later phases (multi-language, RAG).

**Testing:** Unit tests (storage, hashing, ignore) and integration tests (init, summarize with mocked LLM, export) live under `tests/`; see **[tests/README.md](../../tests/README.md)** for how to run and what’s covered.

---

*Keep this doc in sync with the project plan as we implement.*
