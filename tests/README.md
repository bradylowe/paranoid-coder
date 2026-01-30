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

---

## Coverage

**Unit tests** (`tests/unit/`) exercise core logic in isolation with temp dirs and in-memory/on-disk SQLite:

| Module | What’s tested |
|--------|----------------|
| **test_hashing.py** | `content_hash` (determinism, binary/unicode, non-file raises); `tree_hash` (empty dir, from children, change propagation); `needs_summarization` (missing/same/different hash, Path vs str). |
| **test_ignore.py** | `parse_ignore_file` (missing, comments/blanks, patterns); `build_spec` / `is_ignored` (empty, globs, dirs, combined, str paths); `load_patterns` (builtin, additional, .paranoidignore, .gitignore on/off); `sync_patterns_to_storage`; full flow. |
| **test_storage.py** | SQLiteStorage: set/get/upsert/delete summary, `list_children` (direct only, empty, path normalize), metadata get/set, ignore patterns, `.paranoid-coder` creation, `needs_update`, `get_stats` (empty, by type/model, scoped), `get_all_summaries` (empty, scoped). |

**Integration tests** (`tests/integration/`) run real commands (init, summarize, export) against a copied fixture project; Ollama is **mocked** so no LLM or network is used:

| Module | What’s tested |
|--------|----------------|
| **test_init.py** | `paranoid init` creates `.paranoid-coder/` and `summaries.db`; init on a subpath creates DB in that directory. |
| **test_summarize.py** | Init + summarize (mocked LLM) writes summaries to DB; dry-run writes no rows; summarize without init exits with error. |
| **test_export.py** | After init + summarized (mocked), `export --format json` and `--format csv` produce valid JSON array / CSV with expected fields. |

Integration tests use the **testing_grounds/** fixture; if that directory is missing, summarize/export tests are skipped.

---

## Not covered (yet)

Per `docs/development/project_plan.md`: viewer, LLM layer (Ollama client), CLI argument parsing, and end-to-end tests with a real Ollama instance are not in this suite.
