# Paranoid – Tests

## How to run

From the repo root (with the package installed, e.g. `pip install -e .`):

```bash
pytest
```

Or explicitly:

```bash
pytest tests/
```

Run only unit or only integration tests:

```bash
pytest tests/unit/
pytest tests/integration/
```

Verbose output: `pytest -v`. Run a single file: `pytest tests/unit/test_storage.py`.

Optional: run with coverage (e.g. `pytest --cov=src/paranoid --cov-report=term-missing`).

---

## Coverage

**Unit tests** (`tests/unit/`) exercise core logic in isolation with temp dirs and on-disk SQLite:

| Module | What’s tested |
|--------|----------------|
| **test_hashing.py** | `content_hash` (determinism, binary/unicode, non-file raises); `tree_hash` (empty dir, from children, change propagation); `needs_summarization` (missing/same/different hash, Path vs str, smart invalidation when context changes). |
| **test_ignore.py** | `parse_ignore_file` (missing, comments/blanks, patterns); `build_spec` / `is_ignored` (empty, globs, dirs, combined, str paths); `load_patterns` (builtin, additional, .paranoidignore, .gitignore on/off); `sync_patterns_to_storage`; full flow. |
| **test_storage.py** | SQLiteStorage: set/get/upsert/delete summary, `list_children` (direct only, empty, path normalize), metadata get/set, ignore patterns, `.paranoid-coder` creation, `needs_update`, `get_stats` (empty, by type/model/language, scoped), `get_all_summaries` (empty, scoped). |
| **test_prompts.py** | `detect_language` (Python, JS/TS, Go, Rust, unknown); `detect_directory_language` (empty, dirs-only, files, tie-breaking); `description_length_for_content`; `get_prompt_keys` / `get_builtin_template`; `set_prompt_overrides` and file/directory prompt using overrides; `load_overrides_from_project` (missing, empty, valid, invalid JSON). |
| **test_context.py** | `get_context_size` (small/medium/large prompts, CONTEXT_MIN, 2**15, 2**16, CONTEXT_MAX); `ContextOverflowException` for prompts exceeding max context. |
| **test_config.py** | `default_config`; `resolve_path`; `get_project_root` (file vs dir); `find_project_root` (not found, found, from file); `project_config_path`. |
| **test_analysis_parser.py** | Parser: `supports_language` (python); unsupported language raises; parse file extracts entities (class, function, method) and relationships (imports, calls); missing file returns empty; docstrings extracted. |

**Integration tests** (`tests/integration/`) run real CLI commands against a copied fixture project; Ollama is **mocked** so no LLM or network is used:

| Module | What’s tested |
|--------|----------------|
| **test_init.py** | `paranoid init` creates `.paranoid-coder/` and `summaries.db`; init on a subpath creates DB in that directory. |
| **test_summarize.py** | Init + summarize (mocked LLM) writes summaries to DB; dry-run writes no rows; summarize without init exits with error. |
| **test_export.py** | After init + summarized (mocked), `export --format json` and `--format csv` produce valid JSON array / CSV with expected fields. |
| **test_stats.py** | After init + summarize (mocked), `paranoid stats` output includes "By type:", "By language:", and "Coverage:". |
| **test_prompts.py** | After init, `paranoid prompts --list` output includes prompt keys (e.g. `python:file`) and "Placeholders:". |
| **test_clean.py** | After init + summarize (mocked), `paranoid clean --pruned --dry-run` leaves the DB unchanged. |
| **test_config.py** | After init, `paranoid config --show` produces valid JSON with expected keys (e.g. `default_model`, `ignore`). |
| **test_analyze.py** | Init + analyze extracts entities and relationships (Python, JS, TS); incremental analyze skips unchanged files; entity-level call/inherit relationships. |

Integration tests use the **testing_grounds/** fixture (copied into a temp dir per test). If `testing_grounds/` is missing, tests that depend on it are skipped.

---

## Fixtures

- **testing_grounds/** (repo root): Example project with Python modules and nested dirs. Used by integration tests for init, summarize, export, stats, prompts, clean, and config. Copy is made per test so the repo is not mutated.

---

## CI/CD

GitHub Actions workflow **`.github/workflows/test.yml`** runs on push and pull_request to `main`/`master`:

- Matrix: Python 3.10, 3.11, 3.12
- Steps: checkout → setup Python → `pip install -e ".[viewer]"` → `pytest tests/unit/` → `pytest tests/integration/`

---

## Not covered (yet)

- **Viewer GUI**: PyQt6 viewer behavior (launch, tree, detail, search) is not automated.
- **Real Ollama**: No end-to-end tests that call a live Ollama instance; all summarize tests mock the LLM.
- **CLI argument parsing**: Coverage is indirect via command runs; no dedicated tests for every CLI flag.
