# Paranoid

**Local-only codebase summarization and analysis via Ollama.** No code or summaries leave your machine.

## Why

Many projects are proprietary or sensitive. Some teams can't send code to cloud APIs. Paranoid gives you AI-generated summaries and navigation **entirely on your machine**—Ollama for the LLM, SQLite for storage, optional PyQt6 viewer. Privacy-first, no telemetry, no remote calls except to localhost.

## What it does

- **Summarize** files and directories with a local LLM (Ollama). Bottom-up tree walk; only changed or new items are sent to the model (content + tree hashing).
- **Store** summaries in each project’s **`.paranoid-coder/`** directory (SQLite). No central server; each repo is self-contained.
- **Respect** `.paranoidignore` and `.gitignore` (gitignore-style) plus built-in patterns so you skip tests, venvs, build artifacts, etc.
- **View** summaries in a desktop GUI (`paranoid view`), **export** to JSON/CSV, **clean** stale or ignored entries, **stats** on coverage.

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

From the **project you want to summarize** (not the paranoid-coder repo):

```bash
cd /path/to/your-project
paranoid summarize . --model qwen3:8b
```

Summaries are written to `your-project/.paranoid-coder/summaries.db`. Then:

```bash
paranoid view .
```

(Requires `.[viewer]` for the GUI.)

## Commands

| Command | Description |
|--------|-------------|
| `paranoid summarize <paths> [--model <model>]` | Summarize files/dirs; creates or updates `.paranoid-coder/summaries.db`. |
| `paranoid view [path]` | Launch desktop viewer (default: current dir). |
| `paranoid stats [path]` | Show summary counts and coverage. |
| `paranoid config [--show \| --set key=value]` | Show or set configuration. |
| `paranoid clean [path] [--pruned \| --stale \| --model ...]` | Remove stale or ignored summaries. |
| `paranoid export [path] [--format json \| csv]` | Export summaries to JSON or CSV. |

Paths are resolved relative to the current directory. Use `--dry-run` to see what would be done without writing.

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
- **Project:** `./.paranoid-coder/config.json` overrides (e.g. model, prompt version, extra ignore patterns).

See `docs/development/project_plan.md` for the full schema and options.

## Status and docs

The package is in **active development** (Phase 1). The CLI and storage layer are in place; hashing, ignore parsing, and the full `summarize` pipeline are in progress. Some commands are stubs.

- **Current focus:** [docs/development/todo.md](docs/development/todo.md)
- **Architecture and roadmap:** [docs/development/project_plan.md](docs/development/project_plan.md)
- **Short context:** [docs/development/context.md](docs/development/context.md)

Legacy MVP scripts in this repo (`local_summarizer.py`, `summaries_viewer.py`) are for reference; the new tool is the `paranoid` CLI and `src/paranoid` package.

## License

[MIT](LICENSE).
