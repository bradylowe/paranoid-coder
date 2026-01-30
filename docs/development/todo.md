# Phase 1: Core Foundation (MVP) – Todo List

**Source:** [project_plan.md](project_plan.md) Phase 1  
**Reference:** Reuse logic from `local_summarizer.py` where applicable; rewrite into proper package structure.

**Goal:** Working end-to-end workflow for single Python project.  
**Deliverables:**
- `paranoid summarize <path> --model <model>` works
- Summaries stored in `.paranoid-coder/summaries.db`
- `.paranoidignore`, `.gitignore`, and built-ins respected
- Change detection prevents redundant re-summarization

---

## 1. Project scaffolding

- [x] Create package layout under `src/paranoid/` per project plan (cli, storage, commands, llm, utils)
- [x] Add `pyproject.toml` with dependencies (ollama, PyQt6 optional), entry point `paranoid`
- [x] Add `src/paranoid/__init__.py` and module `__init__.py` files
- [x] Add `config.py` with default paths, constants, and config loading (global + project overrides)

---

## 2. Storage layer

- [x] **Data models** (`storage/models.py`): Define Summary, IgnorePattern (or equivalent) dataclasses matching schema
- [x] **Abstract interface** (`storage/base.py`): Define Storage interface (get/set summary, list_children, get/set ignore patterns, metadata)
- [x] **SQLite schema** (`storage/sqlite.py`): Implement schema from project plan (summaries, ignore_patterns, metadata tables + indexes)
- [x] **SQLite implementation**: Implement all Storage interface methods (create DB dir, init schema, migrations if needed)
- [x] **Unit tests** (`tests/unit/test_storage.py`): CRUD for summaries, list_children, ignore_patterns, metadata

---

## 3. Hashing utilities

- [ ] **Content hash** (`utils/hashing.py`): SHA-256 of file contents; handle binary/unicode safely
- [ ] **Tree hash**: Compute directory hash from sorted child hashes (per project plan algorithm), using storage to get child hashes
- [ ] **Change detection**: Helper that, given path + current hash, checks storage and returns whether item needs summarization
- [ ] **Unit tests** (`tests/unit/test_hashing.py`): Content hash deterministic, tree hash propagates changes

---

## 4. Ignore pattern support

- [ ] **Settings**: `ignore.builtin_patterns`, `ignore.use_gitignore`, `ignore.additional_patterns` in config
- [ ] **Parser** (`utils/ignore.py`): Read `.paranoidignore` (gitignore syntax); optionally read `.gitignore` when `use_gitignore` is true
- [ ] **Matching**: Function to check a path against combined patterns (builtin + file + gitignore + additional)
- [ ] **Storage**: Persist patterns in `ignore_patterns` table (pattern, source, added_at)
- [ ] **Unit tests** (`tests/unit/test_ignore.py`): Parse sample files, match paths correctly

---

## 5. LLM layer

- [ ] **Ollama client** (`llm/ollama.py`): Wrapper for generate call (model, prompt, options); handle connection errors
- [ ] **Prompts** (`llm/prompts.py`): Versioned prompt templates (file summary, directory summary); `prompt_version` constant
- [ ] **Integration**: Single function “summarize this content with this model” used by summarization command

---

## 6. CLI foundation

- [ ] **Entry point** (`cli.py`): Parse top-level args, dispatch to subcommands (summarize, view, stats, config, clean, export — stubs ok for non-summarize)
- [ ] **Path resolution**: Resolve paths to absolute; determine project root (directory containing `.paranoid-coder` or current dir for init)
- [ ] **Flags**: `--dry-run`, `--verbose`, `--quiet`; wire to logging level
- [ ] **Logging**: Basic logging (console + optional file from config); no secrets in logs

---

## 7. Summarization command

- [ ] **Tree walker** (`commands/summarize.py`): Bottom-up walk (files first, then directories); respect ignore patterns; yield (path, type, content_or_children_info) for each item
- [ ] **Orchestration**: For each item, compute content/tree hash; if unchanged, skip; if changed/new, call LLM, then store summary + metadata (model, model_version, prompt_version, timestamps)
- [ ] **Progress**: Progress indicator (e.g. “X/Y processed”) for files and directories
- [ ] **Error handling**: Per-file/per-dir errors (store in `error` column, continue); Ollama unreachable → clear message and exit
- [ ] **Dry-run**: When `--dry-run`, report what would be summarized/skipped without calling LLM or writing DB

---

## 8. End-to-end and polish

- [ ] **Integration test**: Run `paranoid summarize <fixture_project> --model <model>` (or mock Ollama), verify `.paranoid-coder/summaries.db` and contents
- [ ] **Docs**: Update README with install instructions and “Phase 1” usage (`paranoid summarize . --model qwen3:8b`)
- [ ] **Smoke test**: Manual run on a real Python project; confirm change detection skips unchanged files on second run

---

## Dependency order (suggested)

1. **Scaffolding + config** (1, 6 partial) – so the rest has a home and config exists  
2. **Storage** (2) – summarization and tree hash depend on it  
3. **Hashing** (3) – summarization and change detection depend on it  
4. **Ignore** (4) – tree walk and clean depend on it  
5. **LLM** (5) – summarization depends on it  
6. **CLI** (6) – full subcommand dispatch and flags  
7. **Summarize** (7) – wire storage, hashing, ignore, LLM together  
8. **E2E & polish** (8)

---

*Last updated: January 29, 2026*
