# Paranoid

**Local-only codebase summarization and analysis via Ollama.** No code or summaries leave your machine.

## Why

Many projects are proprietary or sensitive. Some teams can't send code to cloud APIs. Paranoid gives you AI-generated summaries and navigation **entirely on your machine**—Ollama for the LLM, SQLite for storage, optional PyQt6 viewer. Privacy-first, no telemetry, no remote calls except to localhost.

## What it does

- **Summarize** files and directories with a local LLM (Ollama). Bottom-up tree walk; only changed or new items are sent to the model (content + tree hashing; **smart invalidation** re-summarizes when graph context changes for files with `context_level=1`). **Multi-language:** language-specific prompts for Python, JavaScript, TypeScript, Go, Rust, Java, Markdown, and more (detected by extension).
- **Store** summaries in each project’s **`.paranoid-coder/`** directory (SQLite). No central server; each repo is self-contained.
- **Respect** `.paranoidignore` and `.gitignore` (gitignore-style) plus built-in patterns so you skip tests, venvs, build artifacts, etc.
- **View** summaries in a desktop GUI (`paranoid view`), **export** to JSON/CSV, **clean** stale or ignored entries, **stats** (including **by language**), and **customize prompts** (`paranoid prompts --list` / `--edit`).

## Prerequisites

- [Ollama](https://ollama.com/) installed and running.
- A code-capable model, e.g. `ollama pull qwen3:8b` or `qwen2.5-coder:7b`.
- Python 3.10+.

## Installation

```bash
git clone https://github.com/your-org/paranoid-coder.git
cd paranoid-coder
pip install -e .
```

Optional: install with viewer support (PyQt6) or MCP server (for Cursor, Claude Code):

```bash
pip install -e ".[viewer]"
pip install -e ".[mcp]"        # MCP server for AI agents
pip install -e ".[viewer,mcp]" # both
```

## Quick start

From the **project you want to summarize** (or pass its path), initialize once, then analyze (optional) and summarize:

```bash
cd /path/to/your-project
paranoid init
paranoid analyze .                   # optional: extract code graph (fast, no LLM)
paranoid summarize . --model qwen3:8b
# or a subpath:
paranoid summarize src/app --model qwen2.5-coder:7b
```

`paranoid init` is the **only** way to create the `.paranoid-coder/` directory and database. `paranoid analyze` extracts a code graph (entities, imports, calls, inheritance) for Python, JavaScript, and TypeScript—run it before or alongside summarize. All other commands (analyze, doctor, summarize, view, stats, clean, export) look for an existing `.paranoid-coder` by walking up from the given path; if none is found, they print an error and ask you to run `paranoid init` first.

Use `--dry-run` to see what would be summarized or skipped without calling the LLM or writing to the DB:

```bash
paranoid summarize . --dry-run
```

Summaries are written to `<project>/.paranoid-coder/summaries.db`. To ask questions, run `paranoid index .` (after summarize), then ask. **Hybrid ask** routes queries intelligently: usage/definition queries use the code graph (instant, no LLM) when `paranoid analyze` was run; explanation/generation queries use RAG + LLM.

```bash
paranoid analyze .                   # optional: extract code graph (enables graph-backed answers)
paranoid index .
paranoid ask "where is authentication handled?" --sources
paranoid ask "where is greet used?"   # graph path: instant answer if analyze was run
```

Or open the desktop viewer:

```bash
paranoid view .
```

(Requires `pip install -e ".[viewer]"` for the GUI. If PyQt6 isn’t installed, `paranoid view` prints an error and suggests installing the viewer extra.)

**Stats** (summary counts by type and by language, coverage, last update, model breakdown):

```bash
paranoid stats .
paranoid stats src/   # stats for a subtree
```

**Doctor** (documentation quality—requires `paranoid analyze` first):

```bash
paranoid doctor .              # full report
paranoid doctor . --top 20     # top 20 by priority
paranoid doctor . -f json > doc-report.json
```

**Export** to JSON or CSV (writes to stdout; redirect to save):

```bash
paranoid export . --format json > project_summaries.json
paranoid export . --format csv > summaries.csv
paranoid export src/api --format json > api_summaries.json   # subtree only
```

**MCP server** (for Cursor, Claude Code, and other MCP clients): `pip install -e ".[mcp]"`, then run `paranoid-mcp`. See [README_MCP.md](README_MCP.md) for agent-facing documentation.

## Commands

| Command | Description |
|--------|-------------|
| `paranoid init [path]` | **Initialize** a paranoid project (creates `.paranoid-coder/` and DB). Required before other commands. |
| `paranoid analyze [path] [--force]` | **Extract code graph** (entities, imports, calls, inheritance) for Python, JavaScript, TypeScript. Fast, no LLM. Incremental by default. |
| `paranoid doctor [path] [--top N] [--format text \| json]` | **Scan documentation quality** (missing docstrings, examples, type hints). Requires `paranoid analyze` first. Priority score = usage × complexity × public API. `--top N` limits output; `--format json` for tooling. |
| `paranoid summarize <paths> [--model <model>] [--context-level N] [--force]` | Summarize files/dirs; uses existing `.paranoid-coder` (searches upward from path). Language-specific prompts (Python, JS, Go, Rust, etc.). With `paranoid analyze`, file summaries include graph context (imports, callers, callees). `--context-level 0` forces isolated; `1` uses graph when available (default); `2` reserved for RAG. `--force` re-summarizes even when hash/context unchanged. |
| `paranoid view [path]` | Launch desktop viewer (requires `.[viewer]`). Tree (lazy-loaded), detail panel, search by path. View → **Show ignored paths**; right-click: **Copy path**, **Store current hashes** (update hash in DB without re-summarizing), **Re-summarize** (runs summarize with `--force` using `default_model`). Items needing re-summary (content or context changed) shown with amber highlight. Detail panel shows prompt version, context level (Isolated / With graph). |
| `paranoid stats [path]` | Show summary counts by type (files/dirs), **by language** (file count per language), coverage %, last update, and model usage breakdown. Path scopes the stats (e.g. `paranoid stats src/`). |
| `paranoid export [path] [--format json \| csv]` | Export summaries to stdout as JSON (array of summary objects) or flat CSV. Path scopes export (e.g. `paranoid export src/api`). Redirect to save: `paranoid export . -f json > out.json`. |
| `paranoid prompts [path] [--list \| --edit NAME]` | **List** prompt templates (language:kind, built-in vs overridden) or **edit** one (e.g. `python:file`, `javascript:directory`). Overrides saved to `.paranoid-coder/prompt_overrides.json`; used by `paranoid summarize`. |
| `paranoid config [path] [--show \| --set KEY=VALUE \| --add KEY VALUE \| --remove KEY VALUE] [--global]` | Show or edit config (merged: defaults → global → project). Use `--add`/`--remove` for list keys (e.g. `ignore.additional_patterns`). `--global` writes to global config even inside a project. |
| `paranoid clean [path] [--pruned \| --stale \| --model NAME] [--dry-run]` | Remove summaries: `--pruned` (ignored paths), `--stale --days N` (older than N days), `--model` (by model). Path scopes the clean. `--dry-run` previews deletions. |
| `paranoid index [path] [--full] [--summaries-only \| --entities-only \| ...]` | Index summaries and code entities for RAG. Run `paranoid analyze` first to enable entity indexing. `--summaries-only` / `--entities-only` restrict what is indexed. See [user manual](docs/user_manual.md#paranoid-index). |
| `paranoid ask [path] "question" [--sources] [--model M] [--force-rag] [--classifier-model M]` | **Hybrid ask:** LLM classifies query (usage/definition/explanation/generation). Usage/definition → graph (instant); explanation/generation → RAG + LLM. Use **`--sources`** for retrieved paths. **`--force-rag`** skips graph routing. **`--classifier-model`** overrides model for classification. |

Paths are resolved to absolute (from current directory). Commands that take a path (view, stats, export, clean, config, doctor) find the project by walking up from the given path. Use `--dry-run` (summarize) to see what would be done without writing. Global flags: `-v`/`--verbose`, `-q`/`--quiet`.

Re-summarizing an existing path (e.g. from the viewer’s **Re-summarize** or `paranoid summarize ... --force`) updates the summary and **Updated** timestamp but keeps the original **Generated** timestamp.

## Ignoring files

Add a **`.paranoidignore`** in your project (same syntax as `.gitignore`). By default `.gitignore` is also respected. Example:

```
# Tests and generated code
*_test.py
tests/
migrations/
__pycache__/
.venv/
```

## Configuration

- **Global:** `~/.paranoid/config.json` (default model, Ollama host, logging, ignore options).
- **Project:** `./.paranoid-coder/config.json` overrides (e.g. model, `default_context_level`, `smart_invalidation` thresholds, extra ignore patterns).
- **Prompt overrides:** `./.paranoid-coder/prompt_overrides.json` — custom prompt templates per language (e.g. `python:file`, `javascript:directory`). Use `paranoid prompts --list` and `paranoid prompts --edit NAME` to manage; `paranoid summarize` uses them automatically.

Use `paranoid config --show` to see merged config; `--set`, `--add`, `--remove` to edit. See [docs/user_manual.md](docs/user_manual.md) and [docs/development/project_plan.md](docs/development/project_plan.md) for the full schema and options.

## Status and docs

**Phase 1 (MVP), Phase 2 (viewer & UX), Phase 3 (maintenance & docs), Phase 4 (multi-language & prompt management), Phase 5A (Basic RAG), Phase 5B (graph queries & doctor), Phase 5C (Hybrid Ask including entity-level RAG), and Phase 6 (MCP Server) ✅** are complete. Run `paranoid init` first to create `.paranoid-coder/` and the database. **`paranoid analyze`** extracts a code graph (entities, imports, calls, inheritance) for Python, JavaScript, TypeScript. **`paranoid doctor`** scans entities for documentation quality (missing docstrings, examples, type hints) with priority scoring. **Summarize** runs a bottom-up walk with language-specific prompts, skips unchanged items by hash and context (smart invalidation for files with graph context; use `--force` to re-summarize anyway), and stores summaries in `.paranoid-coder/summaries.db`. With `paranoid analyze` run first, file summaries include graph context (imports, callers, callees). **Index** embeds summaries and code entities for RAG (run `paranoid analyze` first to enable entity indexing). **Ask** (hybrid: LLM-based query classification, graph for usage/definition, RAG+LLM for explanation/generation) queries both summaries and entity embeddings; `--sources` shows file:line with code snippets for entity results. **View** launches the PyQt6 GUI: tree (lazy-loaded), detail panel (prompt version, context level), search by path, View → Show ignored paths, needs-re-summary highlight (content or context changed), and context menu (Copy path, Store current hashes, Re-summarize). **Stats** (including by-language breakdown), **export**, **prompts** (list/edit templates), **config**, and **clean** are implemented; all require an initialized project (they search upward for `.paranoid-coder`). See [docs/development/project_plan.md](docs/development/project_plan.md) for the roadmap.

- **User manual:** [docs/user_manual.md](docs/user_manual.md) — installation, quick start, all commands, configuration, `.paranoidignore` examples, workflows, troubleshooting.
- **MCP server (agents):** [README_MCP.md](README_MCP.md) — tool usage, readiness flow, error handling, polling. For AI agents using the Paranoid MCP.
- **Architecture and roadmap:** [docs/development/project_plan.md](docs/development/project_plan.md)
- **Testing:** [tests/README.md](tests/README.md) — how to run tests and what’s covered.

Legacy scripts in this repo (`local_summarizer.py`, `summaries_viewer.py`) are for reference; the main tool is the `paranoid` CLI and `src/paranoid` package.

## License

[MIT](LICENSE).
