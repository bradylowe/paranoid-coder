# Paranoid – User Manual

Local-only codebase summarization and analysis via Ollama. No code or summaries leave your machine.

---

## Installation

**Prerequisites:**

- [Ollama](https://ollama.com/) installed and running
- A code-capable model, e.g. `ollama pull qwen2.5-coder:7b` or `qwen3:8b`
- Python 3.10+

**Install from source:**

```bash
git clone https://github.com/your-org/paranoid-coder.git
cd paranoid-coder
pip install -e .
```

**With viewer (PyQt6 GUI):**

```bash
pip install -e ".[viewer]"
```

---

## Quick start

From the **project you want to summarize** (or pass its path):

```bash
cd /path/to/your-project
paranoid init
paranoid analyze .                    # optional: extract code graph (fast, no LLM)
paranoid summarize . --model qwen2.5-coder:7b
paranoid view .
```

- `paranoid init` creates `.paranoid-coder/` and the SQLite database. Run it once per project.
- `paranoid analyze` extracts a code graph (entities, imports, calls, inheritance) for Python, JavaScript, and TypeScript. Run it before or after summarize; it is fast and uses no LLM.
- All other commands (analyze, doctor, summarize, view, stats, clean, export, config, prompts, ask, index) find the project by walking up from the given path (default: `.`). If no `.paranoid-coder` is found, they ask you to run `paranoid init` first.
- Use `--dry-run` to see what would be summarized without calling the LLM or writing to the DB.

**Multi-language:** Summarize uses language-specific prompts (Python, JavaScript, TypeScript, Go, Rust, Java, Markdown, and more). File language is detected by extension; directory prompts follow the dominant language of their children. Stats show a **By language** breakdown (file counts per language).

**RAG (ask):** After summarizing and indexing, run `paranoid ask "your question?"` to get answers. **Hybrid ask** (Phase 5C) classifies queries with a small LLM: usage/definition queries use the code graph (instant, no answer LLM) when `paranoid analyze` was run; explanation/generation queries use RAG + LLM. See [paranoid ask](#paranoid-ask) and [paranoid index](#paranoid-index).

**Phase 5B (Complete):** Graph extraction (`paranoid analyze`), graph query API (`paranoid.graph`), and documentation quality (`paranoid doctor`) are all implemented.

**Phase 5C (Complete):** Hybrid ask with LLM-based query classification, graph-first routing for usage/definition, RAG for explanation/generation.

---

## Configuration

Config is merged in order: **defaults** → **global** (`~/.paranoid/config.json`) → **project** (`.paranoid-coder/config.json` when inside a project). Project overrides global.

**Main options:**

| Key | Description | Default |
|-----|-------------|---------|
| `default_model` | Ollama model for summarize/viewer Re-summarize | `qwen2.5-coder:7b` |
| `default_embedding_model` | Ollama embedding model for RAG (index, ask) | `nomic-embed-text` |
| `default_classifier_model` | Small model for query classification (ask) | `qwen2.5-coder-cpu:1.5b` |
| `ollama_host` | Ollama API base URL | `http://localhost:11434` |
| `default_context_level` | Summarization context: `null` (auto), `0` (isolated), `1` (with graph), `2` (with RAG, future) | `null` |
| `smart_invalidation.callers_threshold` | Re-summarize when callers increase by more than this | `3` |
| `smart_invalidation.callees_threshold` | Re-summarize when callees increase by more than this | `3` |
| `smart_invalidation.re_summarize_on_imports_change` | Re-summarize when imports change | `true` |
| `viewer.show_ignored` | Show ignored paths in viewer tree | `false` |
| `ignore.use_gitignore` | Respect `.gitignore` | `true` |
| `ignore.additional_patterns` | Extra ignore patterns (list) | `[]` |
| `logging.level` | Root log level | `INFO` |

Use `paranoid config --show` to see the merged config. Use `--set`, `--add`, or `--remove` to change values (see [paranoid config](#paranoid-config) below).

---

## Commands

### `paranoid init`

Initialize a paranoid project. Creates `.paranoid-coder/` and `summaries.db`. Required before any other command.

```bash
paranoid init [path]   # path default: .
```

### `paranoid summarize`

Summarize files and directories with a local LLM. Only changed or new items (by content/tree hash) are sent to the model.

```bash
paranoid summarize <paths> [--model <model>] [--context-level N] [--force]
```

- **paths:** One or more files or directories (e.g. `.` or `src/ app/`).
- **--model:** Ollama model (e.g. `qwen2.5-coder:7b`). Uses `default_model` from config if omitted.
- **--context-level:** `0` = isolated (no graph), `1` = with graph context (default when available), `2` = with RAG (future). Omit for auto (use graph when `paranoid analyze` was run).
- **--force:** Re-summarize even when hash is unchanged (e.g. after changing prompts).
- **--dry-run:** Report what would be done without calling the LLM or writing.

**Language:** Each file is summarized with a prompt tailored to its language (detected by extension). Directory prompts use the dominant language of their direct file children. Custom prompts can override built-in ones (see [paranoid prompts](#paranoid-prompts)).

### `paranoid analyze`

Extract a code graph (entities, imports, calls, inheritance) using static analysis. No LLM calls; runs quickly on large codebases.

```bash
paranoid analyze [path] [--force] [--dry-run]
```

- **path:** Directory or file to analyze (default: `.`).
- **--force:** Re-analyze all files even if unchanged.
- **--dry-run:** Report what would be analyzed without writing.

**Supported languages:** Python, JavaScript, TypeScript (including JSX/TSX). Entities and relationships are stored in the database for future use (e.g. context-rich summarization, graph queries, `paranoid doctor`).

**Workflow:** Run `paranoid analyze .` after init and before or alongside summarize. Incremental by default: only changed files are re-analyzed.

### `paranoid doctor`

Scan code entities for documentation quality. Requires `paranoid analyze` to have been run.

```bash
paranoid doctor [path] [--top N] [--format text|json]
```

- **path:** Project path to scan (default: `.`). Scopes entities to that path and its descendants.
- **--top N:** Show only the top N items by priority score.
- **--format**, **-f:** `text` (default) for human-readable report, `json` for tooling integration.

**Report includes:**
- Missing docstrings (by priority)
- Has docstring but no examples
- Top items by priority (need attention)

**Priority score** combines usage (callers), complexity (lines), and public API (names not starting with `_`). Higher scores indicate entities that would benefit most from better documentation.

**Examples:**

```bash
paranoid doctor .
paranoid doctor . --top 20
paranoid doctor ./src --format json > doc-report.json
```

### `paranoid view`

Launch the desktop viewer (requires `.[viewer]`). Tree (lazy-loaded), detail panel, search by path.

- **View → Show ignored paths:** Toggle visibility of paths that match ignore rules. Stored in project config as `viewer.show_ignored`.
- **Needs re-summary highlight:** Items that need re-summarization (content or context changed) are shown with an amber background. Uses the same logic as `paranoid summarize` (content hash, smart invalidation for graph context).
- **Detail panel metadata:** Shows model, model version, prompt version, context level (Isolated / With graph / With RAG), generated/updated timestamps.
- **Context menu:** Copy path, **Store current hashes** (write current hash to DB without re-summarizing), **Re-summarize** (runs summarize with `--force` using `default_model`).

### `paranoid stats`

Summary counts by type (files/dirs), **by language** (file count per language), coverage, last update, and model breakdown. Path scopes the stats.

```bash
paranoid stats [path]
```

Example output includes a **By language** section (e.g. Python: 145 files, JavaScript: 38 files, …).

### `paranoid export`

Export summaries to stdout as JSON or CSV. Path scopes the export.

```bash
paranoid export [path] [--format json|csv]
paranoid export . -f json > summaries.json
```

### `paranoid config`

Show or edit configuration. Requires at least one of `--show`, `--set`, `--add`, or `--remove`.

**Path scope:** Optional path (default: `.`) determines project. Inside a project, `--set`/`--add`/`--remove` write to `.paranoid-coder/config.json` unless `--global` is used.

| Option | Effect |
|--------|--------|
| `--show` | Print merged config as JSON. |
| `--set KEY=VALUE` | Set a value (dotted keys, e.g. `viewer.theme=dark`). Value parsed as JSON when possible. |
| `--add KEY VALUE` | Append VALUE to list KEY (e.g. `ignore.additional_patterns "*.pyc"`). |
| `--remove KEY VALUE` | Remove VALUE from list KEY. |
| `--global` | With set/add/remove: write to `~/.paranoid/config.json` even inside a project. |

**Examples:**

```bash
paranoid config --show
paranoid config --set default_model=qwen2.5-coder:7b
paranoid config --add ignore.additional_patterns __init__.py
paranoid config --remove ignore.additional_patterns __init__.py
paranoid config --set default_model=qwen3:8b --global
```

### `paranoid clean`

Remove summaries from the database. Requires at least one of `--pruned`, `--stale`, or `--model`.

**Path scope:** The given path (default: `.`) is the scope. Only summaries at or under that path are considered.

| Option | Effect |
|--------|--------|
| `--pruned` | Remove summaries for paths that match current ignore rules. |
| `--stale --days N` | Remove summaries older than N days (default: 30). |
| `--model NAME` | Remove all summaries generated by that model. |
| `--dry-run` | List what would be deleted without changing the DB. |

**Examples:**

```bash
paranoid clean . --pruned --dry-run
paranoid clean . --stale --days 30
paranoid clean ./subdir --model old-model
```

### `paranoid prompts`

List or edit prompt templates used when summarizing. Overrides are stored in `.paranoid-coder/prompt_overrides.json` and used by `paranoid summarize`.

```bash
paranoid prompts [path] [--list]
paranoid prompts [path] --edit <language:kind>
```

- **--list**, **-l:** List all prompt keys (e.g. `python:file`, `javascript:directory`) and whether each is **built-in** or **overridden**. Default when no `--edit` is given.
- **--edit**, **-e NAME:** Edit the prompt for `NAME` (e.g. `python:file`, `javascript:directory`). Opens your editor (`$EDITOR` or `$VISUAL`; on Windows, `notepad` if unset). Saving writes the override to the project; saving an empty template removes the override and falls back to the built-in prompt.

**Placeholders** (must be kept in custom templates):

- **File prompts:** `{filename}`, `{content}`, `{existing}`, `{length}`, `{extension}`
- **Directory prompts:** `{dir_path}`, `{children}`, `{existing}`, `{n_paragraphs}`

**Examples:**

```bash
paranoid prompts --list
paranoid prompts . -l
paranoid prompts --edit python:file
paranoid prompts -e javascript:directory
```

### `paranoid index`

Index summaries for RAG search. Entity and file-content indexing are planned; currently only summaries are indexed.

```bash
paranoid index [path] [--embedding-model M] [--full]
paranoid index . --summaries-only
paranoid index . --full           # full reindex (not incremental)
```

| Option | Description |
|--------|-------------|
| `--embedding-model` | Ollama embedding model (e.g. `nomic-embed-text`). Uses `default_embedding_model` from config if omitted. |
| `--full` | Full reindex from scratch (default: incremental). |
| `--summaries-only` | Index only summaries (default). |

- **path:** Directory (default: `.`).
- **Incremental:** By default only changed or new items are indexed; use `--full` to rebuild from scratch.

**Examples:**

```bash
paranoid summarize .
paranoid index .                    # index summaries (incremental)
paranoid index . --full             # full rebuild
```

*Note:* Entity and file-content indexing are planned for a future release.

### `paranoid ask`

Ask a natural-language question about the codebase. **Hybrid ask** (Phase 5C) classifies queries with a small LLM and routes them:

- **Usage** (e.g. "where is X used?", "who calls X?") → Direct graph query. Instant answer, no LLM for the response. Requires `paranoid analyze` and graph data.
- **Definition** (e.g. "where is X defined?", "find function Y") → Direct graph query. Instant answer. Requires `paranoid analyze`.
- **Explanation** (e.g. "explain X", "how does Y work?") → RAG over summaries + optional graph context + LLM synthesis.
- **Generation** (e.g. "write a test", "generate code") → RAG + LLM with a generation-oriented prompt.

**For graph-backed answers** (usage/definition): Run `paranoid analyze .` first. No index or summarize needed for those queries.

**For RAG-backed answers** (explanation/generation): Run **`paranoid summarize .`** then **`paranoid index .`** first. The command exits with an error if the vector index is empty when RAG is needed.

```bash
paranoid ask "where is user authentication handled?"
paranoid ask "where is greet used?"              # graph path (if analyze was run)
paranoid ask "where is greet defined?"           # graph path
paranoid ask [path] "your question?" --sources
paranoid ask "explain the auth flow" --sources   # RAG path
paranoid ask "write a test for login"            # generation path
```

| Option | Description |
|--------|-------------|
| `--sources` | After the answer, print retrieved sources (path, relevance, preview). For usage queries, shows graph callers. |
| `--force-rag` | Always use RAG; skip graph routing even for usage/definition queries. |
| `--classifier-model` | Override the model used for query classification (default: `default_classifier_model` from config). |
| `--model` | Ollama model for answer generation (RAG path). Uses `default_model` if omitted. |
| `--embedding-model` | Embedding model for RAG retrieval. Uses `default_embedding_model` if omitted. |
| `--top-k`, `--vector-k` | RAG retrieval parameters. |

**Workflow:** For best coverage, run **`paranoid analyze .`**, **`paranoid summarize .`**, and **`paranoid index .`** before using ask. Usage/definition queries work with analyze alone; explanation/generation need summarize + index.

---

## Ignoring files

**`.paranoidignore`** in the project root uses the same syntax as `.gitignore`. By default `.gitignore` is also respected. Built-in patterns (e.g. `.git/`, `.paranoid-coder/`) are always applied.

**Example `.paranoidignore`:**

```
# Tests and generated code
*_test.py
tests/
migrations/
__pycache__/
.venv/
node_modules/
*.pyc
```

**Additional patterns via config** (without editing files):

```bash
paranoid config --add ignore.additional_patterns "*.log"
paranoid config --add ignore.additional_patterns "dist/"
```

---

## Common workflows

**Initial summarize of a project:**

```bash
cd /path/to/project
paranoid init
paranoid analyze .                    # optional: extract code graph first
paranoid summarize . --model qwen2.5-coder:7b
paranoid view .
```

**Re-summarize after adding ignore patterns:**

```bash
paranoid config --add ignore.additional_patterns "*.min.js"
paranoid summarize .   # unchanged items skipped by hash
```

**Remove old summaries and summaries for a retired model:**

```bash
paranoid clean . --stale --days 90 --dry-run   # preview
paranoid clean . --stale --days 90
paranoid clean . --model old-model-name
```

**Export a subtree for sharing or tooling:**

```bash
paranoid export ./src/api --format json > api_summaries.json
```

**Customize prompts for a language:** Edit a built-in template and re-summarize to use it:

```bash
paranoid prompts --edit python:file    # opens editor; save to override
paranoid summarize . --force          # re-run with new prompt
```

**Acknowledge file changes without re-summarizing (viewer):** Right-click a stale (amber) item → **Store current hashes**. The hash in the DB is updated so the item is no longer marked stale until content changes again.

**Check documentation quality:** Scan entities for missing docstrings, examples, and type hints:

```bash
paranoid analyze .                  # extract code graph first
paranoid doctor .                   # full report
paranoid doctor . --top 20           # top 20 by priority
paranoid doctor ./src --format json > doc-report.json
```

**Index for RAG:** After summarization, index for ask:

```bash
paranoid analyze .                  # optional: extract code graph
paranoid summarize .
paranoid index .                    # index summaries
paranoid ask "where is login handled?"
```

**Ask with sources:** See which file or directory summaries were used to answer:

```bash
paranoid ask "where is user authentication handled?" --sources
```

Output includes the answer, then a **Sources** section listing each retrieved path (file or directory), relevance score, and a short preview of the summary.

**Re-index after summarization changes:**

```bash
paranoid summarize src/auth
paranoid index src/auth
```

**Full index rebuild:**

```bash
paranoid index . --full
```

---

## MCP Server (AI agents)

**For AI agents:** See [README_MCP.md](../README_MCP.md) for focused documentation (tools, readiness flow, errors, polling).

**Install with MCP support:**

```bash
pip install -e ".[mcp]"
```

**Run the MCP server** (for Cursor, Claude Code, and other MCP clients):

```bash
paranoid-mcp
```

**Cursor configuration** (`.cursor/mcp.json` or MCP settings):

```json
{
  "mcpServers": {
    "paranoid": {
      "command": "paranoid-mcp"
    }
  }
}
```

**Tools:** `paranoid_init`, `paranoid_ask`, `paranoid_doctor`, `paranoid_stats`, `paranoid_analyze`, `paranoid_summarize`, `paranoid_index`, `paranoid_job_status`, `paranoid_find_usages`, `paranoid_find_definition`, `paranoid_readiness`.

### Path handling

All tools (except `paranoid_job_status`) require `project_path` as an explicit argument. The agent must pass it; no default (e.g. current working directory) is used. Accepts absolute or relative paths; paths are normalized to absolute before use. Example: `paranoid_stats(project_path="/path/to/project")` or `paranoid_ask(project_path=".", question="...")`.

**Structured errors:** All tools return JSON with `error`, `message`, `remedy`, and `next_steps` when something is missing. Use `paranoid_readiness(project_path)` to assess what to run (init, analyze, summarize, index) before other tools.

### Polling strategy for long-running commands

`paranoid_summarize` and `paranoid_index` run **asynchronously** and return immediately with a `job_id`. The agent can:

1. **Poll `paranoid_job_status(job_id)`** every 5–10 seconds to check if the job is `completed` or `failed`. The response includes current project stats when `include_stats=True` (default).

2. **Poll `paranoid_stats(project_path)`** periodically. When `summary count` or `last_updated` changes, summarization or indexing has progressed.

3. **For very long runs** (hours): The MCP job registry is in-memory and is lost on server restart. Recommend running `paranoid summarize` or `paranoid index` via the CLI directly for large projects.

---

## Troubleshooting

**Ollama connection**

- **"Ollama unreachable" / connection errors:** Ensure Ollama is running (`ollama list`). Default host is `http://localhost:11434`. Override with `paranoid config --set ollama_host=http://127.0.0.1:11434` (or your URL).
- **Model not found:** Pull the model first: `ollama pull qwen2.5-coder:7b`. Use the exact name in `--model` or `default_model`.
- **Classifier model missing:** Ask uses a small model for query classification (`qwen2.5-coder-cpu:1.5b` by default). If missing, run `ollama pull qwen2.5-coder-cpu:1.5b` or set `default_classifier_model` in config. On error, ask falls back to RAG for all queries.

**Performance**

- **Summarize is slow:** Use a smaller/faster model (e.g. `qwen2.5-coder:7b`). Run on a subtree first: `paranoid summarize src/ --model ...`. Unchanged files are skipped by hash; use `--dry-run` to confirm.
- **Viewer feels sluggish on large trees:** The tree is lazy-loaded; expanding a directory loads only its direct children. Use the search/filter to narrow by path. Stale check runs when items are created; very wide directories may take a moment.

**No paranoid project**

- **"No paranoid project initialized":** Run `paranoid init` from the project directory (or pass the project path, e.g. `paranoid summarize /path/to/project`).

**Database migration**

- **"Note: Database migrated to schema v2…":** On first run after an upgrade, an existing database may be migrated (e.g. language column added, existing file summaries marked as Python). This happens once per project; subsequent runs do not show the message.

**Viewer**

- **PyQt6 missing:** Install with `pip install -e ".[viewer]"`. On failure, the `paranoid view` command suggests this.
- **Re-summarize fails with "No default model":** Set a model: `paranoid config --set default_model=qwen2.5-coder:7b` (global or project).

---

*Last updated: January 2026*
