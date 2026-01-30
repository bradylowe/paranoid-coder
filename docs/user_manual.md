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
- All other commands (summarize, view, stats, clean, export, config) find the project by walking up from the given path (default: `.`). If no `.paranoid-coder` is found, they ask you to run `paranoid init` first.
- Use `--dry-run` to see what would be summarized without calling the LLM or writing to the DB.

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

### `paranoid view`

Launch the desktop viewer (requires `.[viewer]`). Tree (lazy-loaded), detail panel, search by path.

- **View → Show ignored paths:** Toggle visibility of paths that match ignore rules. Stored in project config as `viewer.show_ignored`.
- **Stale highlight:** Items whose content no longer matches the stored hash are shown with an amber background (files and parent directories).
- **Context menu:** Copy path, **Store current hashes** (write current hash to DB without re-summarizing), **Re-summarize** (runs summarize with `--force` using `default_model`).

### `paranoid stats`

Summary counts by type (files/dirs), coverage, last update, model breakdown. Path scopes the stats.

```bash
paranoid stats [path]
```

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

**Acknowledge file changes without re-summarizing (viewer):** Right-click a stale (amber) item → **Store current hashes**. The hash in the DB is updated so the item is no longer marked stale until content changes again.

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

**Viewer**

- **PyQt6 missing:** Install with `pip install -e ".[viewer]"`. On failure, the `paranoid view` command suggests this.
- **Re-summarize fails with "No default model":** Set a model: `paranoid config --set default_model=qwen2.5-coder:7b` (global or project).

---

*Last updated: January 2026*
