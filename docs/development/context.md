# Paranoid — Development Context

A short, condensed view of what we're building and why. For current tasks see **[todo.md](todo.md)**. For full architecture, schema, and roadmap see **[project_plan.md](project_plan.md)**.

---

## What Paranoid Is

- **Paranoid** is a **local-only** codebase summarization and analysis tool. It helps developers understand and navigate projects by generating hierarchical summaries with a local LLM (Ollama). No code or summaries leave the user's machine.
- **This repo** is the **tool**. It is installed once (e.g. `pip install -e .`) and used to work on **other** codebases. Target projects are arbitrary directories the user wants to summarize—e.g. `my-project`, `other-repo`.
- **Why:** Privacy-first alternative to cloud code analysis; fast incremental updates via content hashing; each project stays self-contained.

---

## What We're Building

- **CLI** (`paranoid`): `summarize`, `view`, `stats`, `config`, `clean`, `export`. Paths are resolved to absolute; storage lives in the target project.
- **Storage:** Each target project has its own **`.paranoid-coder/`** directory with a SQLite database (`summaries.db`). Summaries are keyed by **normalized full path**; hierarchy is implicit (prefix match). Optional project overrides in `.paranoid-coder/config.json`.
- **Summarization:** Bottom-up tree walk; content hash (SHA-256) and tree hash for change detection; only changed or new items go to Ollama; `.paranoidignore` and `.gitignore` (and built-ins) respected.
- **Viewer:** Desktop GUI (PyQt6) to explore the tree and read summaries; reads from the same `.paranoid-coder/summaries.db`.

---

## Key Design Choices

| Topic | Decision |
|-------|----------|
| Storage location | **Distributed:** each target has its own `.paranoid-coder/` (not a central ~/.paranoid-coder). |
| Storage key | Normalized **absolute path** per file/directory. No separate "project" table. |
| Hierarchy | Implicit: "children of X" = entries whose path is under X (prefix + one segment for direct children). |
| Moving a project | Stored paths break; re-summarize or a future `remap` command. |
| RAG (future) | Primary store remains SQLite in the project; separate local vector index for retrieval; keep in sync. |

---

## Current Focus

See **[todo.md](todo.md)** for the Phase 1 checklist (scaffolding, storage, hashing, ignore patterns, summarization command, CLI). The project plan describes later phases (viewer, clean/config/export, multi-language, RAG).

---

*Keep this doc in sync with the project plan as we implement.*
