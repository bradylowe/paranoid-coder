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
paranoid summarize . --model qwen2.5-coder:7b
paranoid view .
```

- `paranoid init` creates `.paranoid-coder/` and the SQLite database. Run it once per project.
- All other commands (summarize, view, stats, clean, export, config, prompts, ask, index) find the project by walking up from the given path (default: `.`). If no `.paranoid-coder` is found, they ask you to run `paranoid init` first.
- Use `--dry-run` to see what would be summarized without calling the LLM or writing to the DB.

**Multi-language:** Summarize uses language-specific prompts (Python, JavaScript, TypeScript, Go, Rust, Java, Markdown, and more). File language is detected by extension; directory prompts follow the dominant language of their children. Stats show a **By language** breakdown (file counts per language).

**RAG (ask):** After summarizing, you can run `paranoid ask "your question?"` to get answers from your summaries. For finer-grained answers (e.g. "where is User.login?"), run **`paranoid index .`** (Phase 5A) to index summaries, code entities, and/or file contents; then use **`paranoid ask`** or **`paranoid chat`** (Phase 5A). See [paranoid ask](#paranoid-ask) and [paranoid index](#paranoid-index).

---

## Configuration

Config is merged in order: **defaults** → **global** (`~/.paranoid/config.json`) → **project** (`.paranoid-coder/config.json` when inside a project). Project overrides global.

**Main options:**

| Key | Description | Default |
|-----|-------------|---------|
| `default_model` | Ollama model for summarize/viewer Re-summarize | `qwen2.5-coder:7b` |
| `ollama_host` | Ollama API base URL | `http://localhost:11434` |
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
paranoid summarize <paths> [--model <model>] [--force]
```

- **paths:** One or more files or directories (e.g. `.` or `src/ app/`).
- **--model:** Ollama model (e.g. `qwen2.5-coder:7b`). Uses `default_model` from config if omitted.
- **--force:** Re-summarize even when hash is unchanged (e.g. after changing prompts).
- **--dry-run:** Report what would be done without calling the LLM or writing.

**Language:** Each file is summarized with a prompt tailored to its language (detected by extension). Directory prompts use the dominant language of their direct file children. Custom prompts can override built-in ones (see [paranoid prompts](#paranoid-prompts)).

### `paranoid view`

Launch the desktop viewer (requires `.[viewer]`). Tree (lazy-loaded), detail panel, search by path.

- **View → Show ignored paths:** Toggle visibility of paths that match ignore rules. Stored in project config as `viewer.show_ignored`.
- **Stale highlight:** Items whose content no longer matches the stored hash are shown with an amber background (files and parent directories).
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

### `paranoid ask`

Ask a natural-language question about the codebase. Uses RAG over indexed data (summaries, and optionally code entities and file contents after running **`paranoid index`**).

```bash
paranoid ask "where is user authentication handled?"
paranoid ask [path] "your question?"
```

- **path:** Optional; scopes the project (default: `.`). Project root is found by walking up for `.paranoid-coder`.
- Results are built from retrieved summaries (and, if indexed, entities and file chunks); the local LLM (Ollama) answers using that context.

**Indexing:** For best results, run **`paranoid index .`** after **`paranoid summarize .`**. You can restrict what is searched (e.g. entities only) with flags; see [paranoid index](#paranoid-index).

*Availability:* Ask over summaries is available now. Enhanced ask over entities and file contents requires **`paranoid index`** (Phase 5A).

### `paranoid index`

Index summaries, code entities, and/or file contents for RAG search. By default, indexes all three types incrementally. Use flags to limit or combine types.

```bash
paranoid index [path]   # default: index summaries, entities, file contents
paranoid index . --summaries-only
paranoid index . --entities-only
paranoid index . --files-only
paranoid index . --summaries --entities
paranoid index . --no-files
paranoid index path/to/file.txt   # single file: chunk and embed content
paranoid index . --full           # full reindex (not incremental)
```

| Option | Default | Description |
|--------|--------|-------------|
| `--summaries` / `--no-summaries` | True | Index file/directory summaries |
| `--entities` / `--no-entities` | True | Index code entities (classes, functions, methods) |
| `--files` / `--no-files` | True | Index raw file contents (chunk + embed) |
| `--summaries-only` | — | Index only summaries |
| `--entities-only` | — | Index only code entities |
| `--files-only` | — | Index only file contents |
| `--full` | False | Full reindex from scratch (not incremental) |

- **path:** Directory (default: `.`) or a single file. For a single file, the command auto-detects and chunks/embeds that file’s content only.
- **Incremental:** By default only changed or new items are indexed; use `--full` to rebuild from scratch.

**Examples:**

```bash
paranoid summarize .
paranoid index .                    # index everything (incremental)
paranoid index . --entities-only    # only code entities (e.g. after code changes)
paranoid index docs/README.md       # index one file’s content
paranoid index . --no-files         # summaries + entities only (faster)
paranoid index . --full             # full rebuild
```

*Availability:* Planned for Phase 5A. See [docs/development/indexing_implementation.md](development/indexing_implementation.md) for the implementation plan.

### `paranoid chat`

Interactive REPL for multi-turn questions about the codebase. Supports commands such as `/snippet <entity>` (show code for an entity) and `/related <entity>` (find related entities). Uses the same indexed data as **`paranoid ask`**; run **`paranoid index .`** first for best results.

```bash
paranoid chat [path]
```

*Availability:* Planned for Phase 5A.

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

**Index for RAG (Phase 5A):** After summarization, index for ask/chat:

```bash
paranoid summarize .
paranoid index .                    # index summaries, entities, file contents
paranoid ask "where is login handled?"
```

**Re-index only code entities after code changes:**

```bash
paranoid summarize src/auth
paranoid index src/auth --entities-only
```

**Index a single file (e.g. new documentation):**

```bash
paranoid index docs/setup.md
```

**Full index rebuild:**

```bash
paranoid index . --full
```

---

## Troubleshooting

**Ollama connection**

- **"Ollama unreachable" / connection errors:** Ensure Ollama is running (`ollama list`). Default host is `http://localhost:11434`. Override with `paranoid config --set ollama_host=http://127.0.0.1:11434` (or your URL).
- **Model not found:** Pull the model first: `ollama pull qwen2.5-coder:7b`. Use the exact name in `--model` or `default_model`.

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
