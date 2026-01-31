# Paranoid

**Local-only codebase summarization and analysis via Ollama.** No code or summaries leave your machine.

## Why

Many projects are proprietary or sensitive. Some teams can't send code to cloud APIs. Paranoid gives you AI-generated summaries and navigation **entirely on your machine**—Ollama for the LLM, SQLite for storage, optional PyQt6 viewer. Privacy-first, no telemetry, no remote calls except to localhost.

## What it does

- **Summarize** files and directories with a local LLM (Ollama). Bottom-up tree walk; only changed or new items are sent to the model (content + tree hashing). **Multi-language:** language-specific prompts for Python, JavaScript, TypeScript, Go, Rust, Java, Markdown, and more (detected by extension).
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

Optional: install with viewer support (PyQt6):

```bash
pip install -e ".[viewer]"
```

## Quick start

From the **project you want to summarize** (or pass its path), initialize once, then summarize:

```bash
cd /path/to/your-project
paranoid init
paranoid summarize . --model qwen3:8b
# or a subpath:
paranoid summarize src/app --model qwen2.5-coder:7b
```

`paranoid init` is the **only** way to create the `.paranoid-coder/` directory and database. All other commands (summarize, view, stats, clean, export) look for an existing `.paranoid-coder` by walking up from the given path; if none is found, they print an error and ask you to run `paranoid init` first.

Use `--dry-run` to see what would be summarized or skipped without calling the LLM or writing to the DB:

```bash
paranoid summarize . --dry-run
```

Summaries are written to `<project>/.paranoid-coder/summaries.db`. Then:

```bash
paranoid view .
```

(Requires `pip install -e ".[viewer]"` for the GUI. If PyQt6 isn’t installed, `paranoid view` prints an error and suggests installing the viewer extra.)

**Stats** (summary counts by type and by language, coverage, last update, model breakdown):

```bash
paranoid stats .
paranoid stats src/   # stats for a subtree
```

**Export** to JSON or CSV (writes to stdout; redirect to save):

```bash
paranoid export . --format json > project_summaries.json
paranoid export . --format csv > summaries.csv
paranoid export src/api --format json > api_summaries.json   # subtree only
```

## Commands

| Command | Description |
|--------|-------------|
| `paranoid init [path]` | **Initialize** a paranoid project (creates `.paranoid-coder/` and DB). Required before other commands. |
| `paranoid summarize <paths> [--model <model>] [--force]` | Summarize files/dirs; uses existing `.paranoid-coder` (searches upward from path). Language-specific prompts (Python, JS, Go, Rust, etc.). `--force` re-summarizes even when hash is unchanged. |
| `paranoid view [path]` | Launch desktop viewer (requires `.[viewer]`). Tree (lazy-loaded), detail panel, search by path. View → **Show ignored paths**; right-click: **Copy path**, **Store current hashes** (update hash in DB without re-summarizing), **Re-summarize** (runs summarize with `--force` using `default_model`). Stale items (content changed) shown with amber highlight. |
| `paranoid stats [path]` | Show summary counts by type (files/dirs), **by language** (file count per language), coverage %, last update, and model usage breakdown. Path scopes the stats (e.g. `paranoid stats src/`). |
| `paranoid export [path] [--format json \| csv]` | Export summaries to stdout as JSON (array of summary objects) or flat CSV. Path scopes export (e.g. `paranoid export src/api`). Redirect to save: `paranoid export . -f json > out.json`. |
| `paranoid prompts [path] [--list \| --edit NAME]` | **List** prompt templates (language:kind, built-in vs overridden) or **edit** one (e.g. `python:file`, `javascript:directory`). Overrides saved to `.paranoid-coder/prompt_overrides.json`; used by `paranoid summarize`. |
| `paranoid config [path] [--show \| --set KEY=VALUE \| --add KEY VALUE \| --remove KEY VALUE] [--global]` | Show or edit config (merged: defaults → global → project). Use `--add`/`--remove` for list keys (e.g. `ignore.additional_patterns`). `--global` writes to global config even inside a project. |
| `paranoid clean [path] [--pruned \| --stale \| --model NAME] [--dry-run]` | Remove summaries: `--pruned` (ignored paths), `--stale --days N` (older than N days), `--model` (by model). Path scopes the clean. `--dry-run` previews deletions. |

Paths are resolved to absolute (from current directory). Commands that take a path (view, stats, export, clean, config) find the project by walking up from the given path. Use `--dry-run` (summarize) to see what would be done without writing. Global flags: `-v`/`--verbose`, `-q`/`--quiet`.

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
- **Project:** `./.paranoid-coder/config.json` overrides (e.g. model, extra ignore patterns).
- **Prompt overrides:** `./.paranoid-coder/prompt_overrides.json` — custom prompt templates per language (e.g. `python:file`, `javascript:directory`). Use `paranoid prompts --list` and `paranoid prompts --edit NAME` to manage; `paranoid summarize` uses them automatically.

Use `paranoid config --show` to see merged config; `--set`, `--add`, `--remove` to edit. See [docs/user_manual.md](docs/user_manual.md) and [docs/development/project_plan.md](docs/development/project_plan.md) for the full schema and options.

## Status and docs

**Phase 1 (MVP), Phase 2 (viewer & UX), Phase 3 (maintenance & docs), and Phase 4 (multi-language & prompt management) are complete.** Run `paranoid init` first to create `.paranoid-coder/` and the database. **Summarize** runs a bottom-up walk with language-specific prompts (Python, JavaScript, TypeScript, Go, Rust, Java, Markdown, etc.), skips unchanged items by hash (use `--force` to re-summarize anyway), and stores summaries in `.paranoid-coder/summaries.db`. **View** launches the PyQt6 GUI: tree (lazy-loaded), detail panel, search by path, View → Show ignored paths, stale highlight (amber), and context menu (Copy path, Store current hashes, Re-summarize). **Stats** (including by-language breakdown), **export**, **prompts** (list/edit templates), **config**, and **clean** are implemented; all require an initialized project (they search upward for `.paranoid-coder`). **Ask** (RAG over summaries) is available; **Phase 5A** will add **`paranoid index`** (index summaries, code entities, and/or file contents; `--summaries-only`, `--entities-only`, `--files-only`, single-file, `--full`), enhanced ask, and interactive **chat** (`paranoid chat` with `/snippet`, `/related`). See [docs/development/project_plan.md](docs/development/project_plan.md) and [docs/development/indexing_implementation.md](docs/development/indexing_implementation.md) for the roadmap and indexing plan.

- **User manual:** [docs/user_manual.md](docs/user_manual.md) — installation, quick start, all commands, configuration, `.paranoidignore` examples, workflows, troubleshooting.
- **Architecture and roadmap:** [docs/development/project_plan.md](docs/development/project_plan.md)
- **Todo and context:** [docs/development/todo.md](docs/development/todo.md), [docs/development/context.md](docs/development/context.md)
- **Testing:** [tests/README.md](tests/README.md) — how to run tests and what’s covered.

Legacy scripts in this repo (`local_summarizer.py`, `summaries_viewer.py`) are for reference; the main tool is the `paranoid` CLI and `src/paranoid` package.

## License

[MIT](LICENSE).
