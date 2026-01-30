# Paranoid – Project Plan

**Version:** 1.0  
**Date:** January 2026  
**Status:** Planning Phase

---

## Executive Summary

**Paranoid** is a local-only codebase summarization and analysis tool that helps developers understand and navigate complex projects. It generates hierarchical summaries of code using local LLMs (via Ollama), stores them in distributed SQLite databases within each project, and provides a desktop viewer for exploration. The tool maintains strict privacy guarantees: no code or summaries ever leave the user's machine.

**Key Differentiators:**
- **100% Local:** All processing (LLM inference, embeddings, storage) happens on the user's machine
- **Distributed Storage:** Each project maintains its own `.paranoid-coder/` directory with SQLite database
- **Smart Change Detection:** Content-based hashing with hierarchical tree hashing for efficient incremental updates
- **Multi-Model Support:** Works with any Ollama-compatible model, tracking which model/version generated each summary

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Storage Design](#storage-design)
3. [Project Structure](#project-structure)
4. [Feature Roadmap](#feature-roadmap)
5. [User Workflows](#user-workflows)
6. [Technical Specifications](#technical-specifications)

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         paranoid CLI                        │
│  (installed globally via pip install -e .)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Command Layer                           │
│  init │ summarize │ view │ stats │ config │ clean │ export  │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
│  Storage Layer   │  │  LLM Layer   │  │   Viewer Layer   │
│  (SQLite + API)  │  │  (Ollama)    │  │   (PyQt6 GUI)    │
└──────────────────┘  └──────────────┘  └──────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│              Target Project Filesystem                      │
│  /path/to/project/.paranoid-coder/summaries.db              │
│                                                             │
│  Stores:                                                    │
│  - File/directory summaries                                 │
│  - Content hashes (SHA-256)                                 │
│  - Tree hashes (hierarchical change detection)              │
│  - Model metadata (name, version, prompts)                  │
│  - Ignore patterns with timestamps                          │
│  - Generation timestamps                                    │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User runs** `paranoid init` (once per project) to create `.paranoid-coder/` and `summaries.db`.
2. **User runs:** `paranoid summarize module1 module2 --model qwen3:8b`
3. **CLI resolves** paths to absolute, finds project root by walking upward for `.paranoid-coder` (errors if not found), opens `.paranoid-coder/summaries.db`
4. **Summarizer walks** directory tree bottom-up (files first, then directories)
5. **For each item:**
   - Compute content hash (SHA-256 of file content or sorted child hashes)
   - Check if hash matches database → skip if unchanged
   - If changed/new → send to Ollama → store summary + metadata
6. **Storage layer** records: path, type, hash, description, model info, timestamp
7. **Viewer** reads from same database, shows tree structure with lazy-loading

---

## Storage Design

### Distributed Local Storage

Each target project gets its own `.paranoid-coder/` directory containing:

```
/path/to/my-project/
├── .paranoid-coder/
│   ├── summaries.db          # SQLite database (primary storage)
│   ├── .paranoid-coder-id    # Project fingerprint (future: for portability)
│   └── config.json           # Project-specific overrides (optional)
├── .paranoidignore           # Gitignore-style patterns
├── .gitignore                # Gitignore-style patterns
├── src/
├── tests/
└── ...
```

**Why distributed?**
- Projects are self-contained and portable
- No central database bloat from old/deleted projects
- Natural isolation between unrelated codebases
- Can be version-controlled (user's choice whether to commit `.paranoid-coder/`)
- Backup/sync follows project structure

**Version control considerations:**
- `.paranoid-coder/` should generally be gitignored (summaries are derived data)
- Exception: Teams could commit summaries to share AI-generated documentation
- `.paranoidignore` should be committed (like `.gitignore`)

### Database Schema

**SQLite schema (`summaries.db`):**

```sql
-- Primary summaries table
CREATE TABLE summaries (
    path TEXT PRIMARY KEY,              -- Absolute normalized path
    type TEXT NOT NULL,                 -- 'file' or 'directory'
    hash TEXT NOT NULL,                 -- SHA-256 of file OR folder content
    description TEXT NOT NULL,          -- LLM-generated summary
    file_extension TEXT,                -- e.g., ".py" or NULL for directories
    error TEXT,                         -- Error message if summarization failed
    needs_update BOOLEAN DEFAULT 0,     -- Flag for manual re-summarization
    
    -- Model metadata
    model TEXT NOT NULL,                -- e.g., "qwen3:8b"
    model_version TEXT,                 -- Ollama-reported version
    prompt_version TEXT NOT NULL,       -- Internal prompt versioning
    context_level INTEGER DEFAULT 0,    -- 0 = isolated, 1 = with-parent, 2 = with-rag
    
    -- Timestamps
    generated_at TIMESTAMP NOT NULL,    -- When summary was created
    updated_at TIMESTAMP NOT NULL,      -- Last modification time
    
    -- Future extensions
    tokens_used INTEGER,                -- Token count for cost tracking
    generation_time_ms INTEGER          -- Performance metrics
);

CREATE INDEX idx_type ON summaries(type);
CREATE INDEX idx_updated_at ON summaries(updated_at);
CREATE INDEX idx_needs_update ON summaries(needs_update);

-- Ignore patterns table
CREATE TABLE ignore_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,              -- Glob pattern (e.g., "*.pyc", "node_modules/")
    added_at TIMESTAMP NOT NULL,        -- When pattern was added
    source TEXT                         -- 'file' (.paranoidignore) or 'command' (CLI flag)
);

CREATE INDEX idx_ignore_source ON ignore_patterns(source);

-- Project metadata
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Store project root, creation time, etc.
INSERT INTO metadata (key, value) VALUES 
    ('project_root', '/absolute/path/to/project'),
    ('created_at', '2026-01-29T12:00:00Z'),
    ('version', '1');
```

### Tree Hash Algorithm

For efficient change detection, each directory stores a **tree hash**:

```python
def compute_tree_hash(directory_path: str, storage: Storage) -> str:
    """
    Compute hash for a directory based on its children.
    
    Algorithm:
    1. Get all direct children from storage
    2. Grab the hash of each child object (files and folders)
    3. Sort the hashes to ensure deterministic ordering
    4. Hash the concatenated sorted hashes
    
    Result: Any change to any descendant propagates up to all ancestors.
    """
    children = storage.list_children(directory_path)
    child_hashes = sorted([c.hash for c in children])
    combined = ''.join(child_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()
```

**Benefits:**
- Single hash comparison detects if *anything* in a subtree changed
- No need to recursively check all descendants
- Enables quick "what's stale?" queries

### Ignore Patterns

**`.paranoidignore` file** (gitignore syntax):

```
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so

# Dependencies
node_modules/
venv/
.venv/

# IDE
.vscode/
.idea/
*.swp

# Build artifacts
build/
dist/
*.egg-info/

# Paranoid's own storage
.paranoid-coder/
```

**Workflow:**
1. Parser reads `.paranoidignore` on each run
2. If option `ignore.use_gitignore` is True (default), parser also reads `.gitignore`
3. Patterns stored in `ignore_patterns` table with timestamp
4. During tree walk, check each path against active patterns
5. `paranoid clean --pruned` removes summaries for currently-ignored paths
6. Viewer can optionally hide ignored paths (checkbox in UI)

**NOTE**:  Built-in patterns exist in settings `ignore.builtin_patterns`

---

## Project Structure

```
paranoid-coder/
├── pyproject.toml              # Package definition, dependencies, entry points
├── README.md                   # User-facing documentation
├── LICENSE                     # MIT license
├── .gitignore
│
├── src/
│   └── paranoid/               # Main package (note: no hyphen in Python package)
│       ├── __init__.py
│       ├── cli.py              # Entry point: argument parsing, subcommand dispatch
│       ├── config.py           # Configuration: default paths, constants
│       │
│       ├── storage/            # Storage abstraction layer
│       │   ├── __init__.py
│       │   ├── base.py         # Abstract Storage interface
│       │   ├── sqlite.py       # SQLite implementation
│       │   └── models.py       # Data models (Summary, IgnorePattern, etc.)
│       │
│       ├── commands/           # CLI subcommands
│       │   ├── __init__.py
│       │   ├── summarize.py    # Core summarization logic
│       │   ├── view.py         # Launch viewer
│       │   ├── stats.py        # Show statistics
│       │   ├── config.py       # Show/edit configuration
│       │   ├── clean.py        # Clean stale/ignored summaries
│       │   └── export.py       # Export summaries to JSON/CSV
│       │
│       ├── llm/                # LLM integration
│       │   ├── __init__.py
│       │   ├── ollama.py       # Ollama client wrapper
│       │   └── prompts.py      # Prompt templates with versioning
│       │
│       ├── viewer/             # Desktop GUI
│       │   ├── __init__.py
│       │   ├── app.py          # Main window
│       │   ├── tree_widget.py  # Tree view with lazy loading
│       │   ├── detail_widget.py # Detail panel
│       │   └── search_widget.py # Search/filter UI
│       │
│       └── utils/              # Shared utilities
│           ├── __init__.py
│           ├── hashing.py      # Content and tree hash functions
│           ├── path_utils.py   # Path normalization, ignore matching
│           └── ignore.py       # .paranoidignore parser
│
├── docs/
│   ├── development/
│   │   ├── context.md
│   │   ├── proposed_project_layout.md
│   │   └── project_plan.md    # This document
│   │
│   └── user_guide/
│       ├── installation.md
│       ├── quickstart.md
│       └── configuration.md
│
├── tests/
│   ├── unit/
│   │   ├── test_storage.py
│   │   ├── test_hashing.py
│   │   └── test_ignore.py
│   │
│   ├── integration/
│   │   ├── test_summarize.py
│   │   └── test_viewer.py
│   │
│   └── fixtures/
│       └── testing_grounds/    # Example projects for testing
│           ├── simple_python/  # Single module
│           ├── nested_project/ # Deep hierarchy
│           ├── mixed_files/    # Python + JS + Markdown
│           ├── edge_cases/     # Empty dirs, symlinks, binary files
│           └── with_ignores/   # Test .paranoidignore behavior
│
└── scripts/                    # Development utilities
    ├── migrate_legacy.py       # Migrate old summaries.json to SQLite
    └── benchmark.py            # Performance testing
```

---

## Feature Roadmap

### Phase 1: Core Foundation (MVP)
**Target:** 4-6 weeks

**Goal:** Working end-to-end workflow for single Python project

- [x] Project planning and architecture design
- [x] **Storage layer**
  - [x] SQLite backend implementation
  - [x] Schema creation and migrations
  - [x] Abstract storage interface
  - [x] Unit tests for storage operations
- [x] **Hashing utilities**
  - [x] Content hash (SHA-256 of file contents)
  - [x] Tree hash (recursive directory hashing)
  - [x] Change detection logic
- [x] **Ignore pattern support**
  - [x] `ignore.builtin_patterns` option in settings
  - [x] `.paranoidignore` parser (gitignore syntax)
  - [x] `ignore.use_gitignore` option in settings
  - [x] Pattern matching against paths
  - [x] Store patterns in database
- [x] **Summarization command**
  - [x] Directory tree walker (bottom-up)
  - [x] Ollama integration
  - [x] Prompt templates with versioning
  - [x] Progress indicators
  - [x] Error handling and recovery
- [x] **CLI foundation**
  - [x] Argument parsing (argparse or click)
  - [x] Subcommand dispatch
  - [x] Path resolution (relative → absolute)
  - [x] `--dry-run` flag
  - [x] Basic logging

**Deliverables:**
- `paranoid summarize <path> --model <model>` works
- Summaries stored in `.paranoid-coder/summaries.db`
- `.paranoidignore`, `.gitignore`, and built-ins respected
- Change detection prevents redundant re-summarization

---

### Phase 2: Viewer & User Experience
**Target:** 2-3 weeks

**Goal:** Desktop GUI for exploring summaries

- [x] **PyQt6 viewer application**
  - [x] Main window with menu bar
  - [x] Tree view with lazy loading (fetch children on expand)
  - [x] Detail panel showing summary + metadata
  - [x] Search/filter widget (by path, content, model)
  - [x] Context menu (refresh, re-summarize, copy path)
- [x] **View command**
  - [x] Launch viewer from CLI: `paranoid view .`
  - [x] Pass project root to viewer
  - [x] Handle viewer not installed gracefully
- [x] **Stats command**
  - [x] Show summary count by type (files/dirs)
  - [x] Coverage percentage (summarized vs. total)
  - [x] Last update time
  - [x] Model usage breakdown
- [x] **Export command**
  - [x] `paranoid export . --format json` → JSON dump
  - [x] `paranoid export . --format csv` → Flat CSV
  - [x] Optional filtering by path prefix

**Deliverables:**
- `paranoid view .` launches GUI showing project tree
- User can navigate, search, and inspect summaries
- `paranoid stats .` shows summary metrics
- `paranoid export . --format json` works

---

### Phase 3: Maintenance & Cleanup
**Target:** 2 weeks

**Goal:** Tools for managing summary lifecycle

- [ ] **Clean command**
  - [ ] `paranoid clean --pruned` removes summaries for ignored paths
  - [ ] `paranoid clean --stale --days 30` removes old summaries
  - [ ] `paranoid clean --model old-model` removes specific model's summaries
  - [ ] Dry-run mode to preview deletions
- [ ] **Config command**
  - [ ] `paranoid config --show` displays current settings
  - [ ] `paranoid config --set key=value` for overrides
  - [ ] Support for project-local `.paranoid-coder/config.json`
- [ ] **Viewer enhancements**
  - [ ] Show/hide ignored paths (checkbox)
  - [ ] Highlight stale summaries (hash mismatch)
  - [ ] "Refresh" action to re-compute hashes
  - [ ] "Re-summarize" action for selected items
- [ ] **Documentation**
  - [ ] User guide: installation, quickstart, configuration
  - [ ] Examples: `.paranoidignore` patterns, common workflows
  - [ ] Troubleshooting: Ollama connection, performance

**Deliverables:**
- `paranoid clean` with multiple modes
- `paranoid config` for settings management
- Comprehensive user documentation

---

### Phase 4: Multi-Language & Advanced Features
**Target:** 3-4 weeks

**Goal:** Support non-Python projects and power-user features

- [ ] **Multi-language support**
  - [ ] JavaScript/TypeScript detection and summarization
  - [ ] Go, Rust, Java language-specific prompts
  - [ ] Markdown/documentation file handling
  - [ ] Generic fallback for unknown file types
- [ ] **Prompt management**
  - [ ] Versioned prompt templates
  - [ ] `paranoid prompts --list` to show available prompts
  - [ ] `paranoid prompts --edit <name>` to customize
  - [ ] Track prompt version used for each summary
- [ ] **Incremental updates**
  - [ ] `paranoid summarize --changed-only` uses tree hashes
  - [ ] Only re-summarize paths with hash mismatches
  - [ ] Progress bar shows "X/Y changed, Z skipped"
- [ ] **Testing infrastructure**
  - [ ] Unit tests for all core modules (80%+ coverage)
  - [ ] Integration tests for end-to-end workflows
  - [ ] Fixtures: diverse test projects
  - [ ] CI/CD: automated testing on push

**Deliverables:**
- Works on JavaScript, Go, Rust projects
- Customizable prompts
- Fast incremental updates
- Comprehensive test suite

---

### Phase 5: Future Enhancements (Post-MVP)
**Target:** 6+ months

**Goal:** Advanced features and ecosystem growth

- [ ] **RAG (Retrieval-Augmented Generation)**
  - [ ] Embed summaries using local embedding model
  - [ ] Vector store integration (Chroma, LanceDB, or sqlite-vec)
  - [ ] `paranoid ask "where is user authentication handled?"`
  - [ ] Context-aware code navigation
- [ ] **Code generation**
  - [ ] `paranoid generate readme .` creates README from summaries
  - [ ] `paranoid generate docs .` generates documentation site
  - [ ] Template system for custom generators
- [ ] **Analysis tools**
  - [ ] `paranoid analyze complexity` identifies complex modules
  - [ ] `paranoid analyze dependencies` visualizes module relationships
  - [ ] `paranoid analyze bottlenecks` suggests refactoring targets
- [ ] **Project fingerprinting**
  - [ ] `.paranoid-coder-id` for portability across machines
  - [ ] Git integration: use repo URL + commit as fingerprint
  - [ ] `paranoid remap /old/path /new/path` for moved projects
- [ ] **Collaboration features**
  - [ ] Share summaries via export/import
  - [ ] Diff summaries between versions
  - [ ] Team-wide prompt libraries
- [ ] **Web UI**
  - [ ] Optional web server: `paranoid serve --port 8080`
  - [ ] Browser-based viewer for remote access
  - [ ] REST API for integrations
- [ ] **Performance optimizations**
  - [ ] Parallel summarization (multi-threading/multi-processing)
  - [ ] LRU cache for frequently accessed summaries
  - [ ] Batch processing for large projects

**Long-term vision:**
- Paranoid becomes the standard tool for AI-assisted codebase exploration
- Plugin ecosystem for custom analyzers and generators
- IDE integrations (VS Code, JetBrains)
- Industry adoption for onboarding, documentation, and code review

---

## User Workflows

### Workflow 1: Initial Setup and Summarization

```bash
# Install paranoid globally
git clone https://github.com/user/paranoid-coder.git
cd paranoid-coder
pip install -e .

# Navigate to a project you want to understand
cd ~/projects/my-web-app

# Initialize the project (creates .paranoid-coder/ and summaries.db; required once)
paranoid init

# Run initial summarization with your preferred model
paranoid summarize . --model qwen3:8b

# Output:
# Scanning project structure...
# Found 147 files, 23 directories
# Processing files (bottom-up)...
# [██████████████████████████] 147/147 files (23 skipped via .paranoidignore)
# Processing directories...
# [██████████████████████████] 23/23 directories
# Summaries stored in .paranoid-coder/summaries.db
# Total time: 3m 42s

# View results
paranoid view .
```

### Workflow 2: Incremental Updates

```bash
# Make changes to your code
vim src/auth/login.py

# Re-run summarization (only changed files processed)
paranoid summarize src/auth --model qwen3:8b

# Output:
# Scanning src/auth...
# Found 8 files, 2 directories
# Checking hashes...
# Changed: 1 file, 2 directories (ancestor update)
# Unchanged: 7 files
# [███████               ] 3/10 processed
# Summaries updated
# Total time: 8s
```

### Workflow 3: Exploring Large Codebase

```bash
# Open viewer
paranoid view .

# In viewer:
# - Tree shows project structure
# - Click "src/" → expands to show subdirectories (lazy loaded)
# - Click "auth/" → expands to show files
# - Click "login.py" → detail panel shows:
#   * Summary: "Handles user login via JWT authentication..."
#   * Model: qwen3:8b
#   * Last updated: 2026-01-29 14:23:45
#   * Content hash: a3f8e9...
# - Use search bar: "authentication" → highlights matching items
# - Right-click → "Re-summarize with different model"
```

### Workflow 4: Ignoring Files

```bash
# Create .paranoidignore
cat > .paranoidignore << EOF
# Ignore test files
*_test.py
tests/

# Ignore generated code
migrations/
EOF

# Clean existing summaries for now-ignored paths
paranoid clean --pruned --dry-run
# Output:
# Would remove 23 summaries:
#   - tests/ (12 files, 2 directories)
#   - migrations/ (7 files, 2 directories)

# Confirm and execute
paranoid clean --pruned
```

### Workflow 5: Exporting for Documentation

```bash
# Export all summaries to JSON
paranoid export . --format json > project_summaries.json

# Export only specific module
paranoid export src/api --format csv > api_docs.csv

# Use exported data in documentation generator
cat project_summaries.json | jq '.[] | select(.type=="directory") | .description'
```

### Workflow 6: Multi-Project Management

```bash
# Each project maintains its own summaries; init once per project
cd ~/projects/project-a
paranoid init
paranoid summarize .
# Writes to ~/projects/project-a/.paranoid-coder/summaries.db

cd ~/projects/project-b
paranoid init
paranoid summarize .
# Writes to ~/projects/project-b/.paranoid-coder/summaries.db

# No cross-project interference
# Each project is self-contained
```

---

## Technical Specifications

### Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Hash computation | <5ms per file | Enable fast change detection |
| Tree walk | >1000 files/sec | Keep overhead minimal |
| Database queries | <10ms per lookup | Responsive viewer UI |
| Lazy loading | <100ms per node | Smooth tree expansion |
| Summarization | 1-5 files/sec | Depends on LLM speed (acceptable) |
| Storage overhead | <1% of project size | Summaries are lightweight |

### Dependencies

**Core (required):**
- Python 3.10+
- `ollama` (Python client for Ollama API)
- `sqlite3` (built-in)

**Optional (viewer):**
- `PyQt6` (GUI framework)

**Development:**
- `pytest` (testing)
- `ruff` (linting/formatting)
- `mypy` (type checking)

### Configuration Files

**`~/.paranoid/config.json`** (global defaults):

```json
{
  "default_model": "qwen3:8b",
  "ollama_host": "http://localhost:11434",
  "viewer": {
    "theme": "light",
    "font_size": 10,
    "show_ignored": false
  },
  "logging": {
    "level": "INFO",
    "file": "~/.paranoid/paranoid.log"
  },
  "ignore": {
    "use_gitignore": true,
    "builtin_patterns": [".git/", ".paranoid-coder/"],
    "additional_patterns": []
  }
}
```

**`<project>/.paranoid-coder/config.json`** (project-specific overrides):

```json
{
  "model": "deepseek-coder:7b",
  "prompt_version": "v2.1",
  "ignore": {
    "use_gitignore": false,
    "additional_patterns": ["*.generated.py", "vendor/"]
  }
}
```

### Error Handling

**Graceful degradation:**
- Ollama not running → Clear error message with instructions
- Database corruption → Attempt repair or offer rebuild
- Invalid paths → Helpful error, suggest `paranoid stats` to check
- Out of disk → Fail fast with cleanup instructions

**Logging:**
- Default: INFO level (show progress, summaries)
- `--verbose`: DEBUG level (show hash computations, API calls)
- `--quiet`: ERROR level (only failures)
- All logs → `~/.paranoid/paranoid.log` (configurable)

### Security Considerations

**Local-only guarantee:**
- No network calls except to local Ollama (localhost:11434)
- Explicit user consent before any external network access (future features)
- Clear documentation of privacy model

**File system safety:**
- Never modify source files (read-only access)
- Only write to `.paranoid-coder/` directory
- Validate all paths to prevent directory traversal

**Database safety:**
- Use parameterized queries (prevent SQL injection)
- File permissions: `.paranoid-coder/` directory 0755, `summaries.db` 0644
- Atomic writes (use transactions)

---

## Success Metrics

**MVP success criteria:**

1. **Functionality:** User can summarize a 500+ file Python project in <10 minutes
2. **Accuracy:** LLM summaries are coherent and useful (manual review)
3. **Performance:** Incremental updates 10x faster than full re-summarization
4. **Usability:** Viewer loads projects with 1000+ summaries without lag
5. **Reliability:** Zero data loss (all summaries recoverable from database)

**Long-term adoption metrics:**

- GitHub stars: 1000+ (community interest)
- Active users: 500+ (monthly active installations)
- Supported languages: 5+ (Python, JS, Go, Rust, Java)
- Plugin ecosystem: 10+ community-contributed analyzers

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Ollama model quality varies | Users get poor summaries | Support multiple models, prompt tuning, quality benchmarks |
| Large codebases (10k+ files) slow | Poor UX | Optimize hashing, parallel processing, incremental updates |
| SQLite database corruption | Data loss | Regular backups, repair tools, export functionality |
| Cross-platform compatibility | Windows/Mac users blocked | Test on all platforms, use pathlib, avoid shell commands |
| LLM hallucinations | Misleading summaries | Disclaimer in UI, versioning for re-summarization |

---

## Conclusion

Paranoid is designed to be a **privacy-first, developer-friendly tool** for understanding codebases through AI-generated summaries. The distributed storage model, combined with smart change detection and a polished viewer, positions it as a practical alternative to cloud-based code analysis tools.

**Next steps:**
1. Implement Phase 1 (Core Foundation) over 4-6 weeks
2. Gather feedback from early adopters
3. Iterate on UX based on real-world usage
4. Expand to multi-language support and advanced features

**Questions or feedback?** Open an issue or discussion on the GitHub repository.

---

*Last updated: January 29, 2026*
