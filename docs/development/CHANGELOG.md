# Paranoid – CHANGELOG

**Completed development history and implementation notes.**

---

## Phase 4: Multi-Language & Advanced Features (Completed)

**Timeline**: 3-4 weeks  
**Status**: ✅ Complete

### Multi-language Support
- ✅ Language detection by file extension
- ✅ Language-specific prompt templates for:
  - Python (`.py`)
  - JavaScript (`.js`)
  - TypeScript (`.ts`, `.tsx`)
  - Go (`.go`)
  - Rust (`.rs`)
  - Java (`.java`)
  - Markdown (`.md`)
  - C/C++ (`.c`, `.cpp`, `.h`, `.hpp`)
  - Ruby (`.rb`)
  - PHP (`.php`)
  - Shell (`.sh`, `.bash`)
  - Generic fallback for unknown types
- ✅ Directory language detection (dominant child language)
- ✅ Language column added to `summaries` table (schema v2)
- ✅ Database migration for existing projects

### Prompt Management
- ✅ Versioned prompt templates in `prompts.py`
- ✅ Prompt override system (`.paranoid-coder/prompt_overrides.json`)
- ✅ `paranoid prompts --list` command
- ✅ `paranoid prompts --edit <language:kind>` command
- ✅ Editor integration ($EDITOR, $VISUAL, notepad on Windows)
- ✅ Placeholder validation (required placeholders must be preserved)
- ✅ Built-in vs. overridden status in listings
- ✅ File and directory prompts for each language

### Testing Infrastructure
- ✅ Unit tests for all core modules:
  - `test_hashing.py` - Content and tree hashing
  - `test_ignore.py` - Ignore pattern parsing and matching
  - `test_storage.py` - SQLite operations, migrations
  - `test_prompts.py` - Language detection, prompt templates
  - `test_context.py` - Context window calculations
  - `test_config.py` - Configuration management
- ✅ Integration tests for end-to-end workflows:
  - `test_init.py` - Project initialization
  - `test_summarize.py` - Summarization with mocked LLM
  - `test_export.py` - JSON and CSV export
  - `test_stats.py` - Statistics generation
  - `test_prompts.py` - Prompt listing
  - `test_clean.py` - Cleanup operations
  - `test_config.py` - Configuration commands
- ✅ Testing fixtures (`testing_grounds/` with sample Python project)
- ✅ CI/CD pipeline (GitHub Actions)
  - Python 3.10, 3.11, 3.12 matrix
  - Automated test runs on push/PR
  - Unit and integration test separation

### Documentation
- ✅ User manual with all commands
- ✅ Configuration reference
- ✅ Workflow examples
- ✅ Troubleshooting guide
- ✅ Testing documentation

---

## Phase 3: Maintenance & Cleanup (Completed)

**Timeline**: 2 weeks  
**Status**: ✅ Complete

### Clean Command
- ✅ `paranoid clean --pruned` - Remove summaries for ignored paths
- ✅ `paranoid clean --stale --days N` - Remove old summaries
- ✅ `paranoid clean --model NAME` - Remove by model
- ✅ `--dry-run` mode for preview
- ✅ Path scoping (clean specific subdirectories)
- ✅ Combination of flags (e.g., `--pruned --model old-model`)

### Config Command
- ✅ `paranoid config --show` - Display merged configuration
- ✅ `paranoid config --set KEY=VALUE` - Set values (dotted keys)
- ✅ `paranoid config --add KEY VALUE` - Append to lists
- ✅ `paranoid config --remove KEY VALUE` - Remove from lists
- ✅ `--global` flag for global config modification
- ✅ JSON value parsing for complex types
- ✅ Project vs. global config resolution
- ✅ Configuration validation

### Viewer Enhancements
- ✅ Show/hide ignored paths (checkbox in View menu)
- ✅ Stale highlighting (amber background for hash mismatches)
- ✅ Context menu:
  - Copy path to clipboard
  - Store current hashes (update DB without re-summarizing)
  - Re-summarize with current default_model
- ✅ Refresh action (re-compute hashes, update stale flags)
- ✅ Settings persistence (show_ignored stored in project config)

### Documentation
- ✅ User guide: installation, quickstart, configuration
- ✅ Command reference with examples
- ✅ `.paranoidignore` pattern examples
- ✅ Common workflows documented
- ✅ Troubleshooting section:
  - Ollama connection issues
  - Performance tips
  - Database migration notes
  - Viewer installation

---

## Phase 2: Viewer & User Experience (Completed)

**Timeline**: 2-3 weeks  
**Status**: ✅ Complete

### PyQt6 Viewer Application
- ✅ Main window with menu bar
- ✅ Tree view widget:
  - Lazy loading (children loaded on expand)
  - File/directory icons
  - Path-based hierarchy
  - Click to select and show details
- ✅ Detail panel:
  - Summary text
  - Metadata (model, timestamps, hash, language)
  - File extension and type
  - Error display (if summarization failed)
- ✅ Search widget:
  - Filter by path (substring match)
  - Highlight matching items in tree
  - Real-time filtering
- ✅ Keyboard shortcuts (Ctrl+F for search, etc.)

### View Command
- ✅ `paranoid view [path]` launches GUI
- ✅ Pass project root to viewer
- ✅ Graceful handling when PyQt6 not installed
- ✅ Error message suggests installing viewer extra
- ✅ Platform-agnostic window management

### Stats Command
- ✅ Summary count by type (files vs. directories)
- ✅ Coverage percentage (summarized vs. total files)
- ✅ Last update timestamp
- ✅ Model usage breakdown (count per model)
- ✅ By-language breakdown (file count per language)
- ✅ Path scoping (stats for subdirectories)
- ✅ Formatted output with clear sections

### Export Command
- ✅ `paranoid export [path] --format json`
  - JSON array of summary objects
  - All fields included (path, type, hash, description, metadata)
- ✅ `paranoid export [path] --format csv`
  - Flat CSV with headers
  - One row per summary
- ✅ Path scoping (export subdirectories only)
- ✅ Output to stdout (user redirects to file)
- ✅ Valid JSON/CSV formatting
- ✅ Error handling for missing projects

### User Experience Improvements
- ✅ Progress indicators for long operations
- ✅ Informative error messages
- ✅ Consistent command-line interface
- ✅ Help text for all commands
- ✅ Path normalization and validation

---

## Phase 1: Core Foundation (MVP) (Completed)

**Timeline**: 4-6 weeks  
**Status**: ✅ Complete

### Storage Layer
- ✅ SQLite backend implementation (`storage/sqlite.py`)
- ✅ Schema creation and versioning
- ✅ Abstract storage interface (`storage/base.py`)
- ✅ Data models (`storage/models.py`):
  - `Summary` dataclass
  - `IgnorePattern` dataclass
  - `Metadata` handling
- ✅ Unit tests for all storage operations
- ✅ Database migrations (schema_version tracking)
- ✅ Transaction support
- ✅ Error handling and validation

### Hashing Utilities
- ✅ Content hash (SHA-256 of file contents)
- ✅ Tree hash (recursive directory hashing)
  - Bottom-up computation
  - Deterministic ordering (sorted child hashes)
  - Change detection via hash comparison
- ✅ `needs_summarization()` function
- ✅ Unit tests for hash computations
- ✅ Binary file handling
- ✅ Unicode handling

### Ignore Pattern Support
- ✅ `.paranoidignore` parser (gitignore syntax)
- ✅ Built-in patterns configuration (`ignore.builtin_patterns`)
- ✅ `.gitignore` integration (`ignore.use_gitignore` option)
- ✅ Pattern matching against paths
- ✅ Glob pattern support (*, **, ?, [])
- ✅ Directory-specific patterns (trailing /)
- ✅ Comment and blank line handling
- ✅ Store patterns in database with timestamps
- ✅ Pattern source tracking (file vs. command)
- ✅ Unit tests for ignore logic

### Summarization Command
- ✅ `paranoid init [path]` - Create `.paranoid-coder/` and database
- ✅ `paranoid summarize <paths>` - Generate summaries
- ✅ Directory tree walker:
  - Bottom-up traversal (files first, then directories)
  - Respect ignore patterns
  - Skip unchanged files (hash comparison)
- ✅ Ollama integration:
  - HTTP client wrapper
  - Model selection
  - Error handling and retries
  - Connection validation
- ✅ Prompt templates with versioning:
  - File prompts (context, existing summary, length)
  - Directory prompts (children summaries)
  - Placeholder substitution
- ✅ Progress indicators:
  - File processing progress bar
  - Directory processing progress bar
  - Skipped file count
  - Time elapsed
- ✅ `--dry-run` flag (preview without LLM calls)
- ✅ `--force` flag (re-summarize unchanged files)
- ✅ Error recovery:
  - Store error messages in database
  - Continue processing on individual failures
  - Summary report at end

### CLI Foundation
- ✅ Argument parsing (argparse)
- ✅ Subcommand dispatch:
  - `init` - Initialize project
  - `summarize` - Generate summaries
  - (Additional commands added in later phases)
- ✅ Path resolution:
  - Relative to absolute conversion
  - Project root detection (walk up for `.paranoid-coder`)
  - Validation and error handling
- ✅ Global flags:
  - `-v`/`--verbose` for debug output
  - `-q`/`--quiet` for minimal output
- ✅ Logging configuration:
  - Console and file logging
  - Level control via config
  - Timestamps and formatting

### Configuration System
- ✅ Default configuration in code
- ✅ Global config (`~/.paranoid/config.json`)
- ✅ Project config (`.paranoid-coder/config.json`)
- ✅ Config merging (defaults → global → project)
- ✅ Schema:
  - `default_model` - Default Ollama model
  - `ollama_host` - Ollama API URL
  - `ignore.use_gitignore` - Respect .gitignore
  - `ignore.builtin_patterns` - Built-in ignore patterns
  - `ignore.additional_patterns` - User-added patterns
  - `logging.level` - Log level (INFO, DEBUG, ERROR)
  - `logging.file` - Log file path
- ✅ JSON parsing and validation

### Project Initialization
- ✅ `.paranoid-coder/` directory creation
- ✅ `summaries.db` creation with schema
- ✅ Metadata initialization (project_root, created_at, version)
- ✅ Error handling for existing projects
- ✅ Path validation

### Deliverables
- ✅ Working `paranoid init` and `paranoid summarize` commands
- ✅ Summaries stored in SQLite database
- ✅ Ignore patterns respected (.paranoidignore, .gitignore, built-ins)
- ✅ Change detection prevents redundant re-summarization
- ✅ Progress indicators and error handling
- ✅ Unit tests for core functionality
- ✅ Basic documentation

---

## Phase 5A: Basic RAG (Partial - In Progress)

**Timeline**: Ongoing  
**Status**: 🔄 Partially Complete

### Completed
- ✅ Vector store integration (sqlite-vec)
- ✅ Embedding generation for summaries
- ✅ `paranoid index` command:
  - Index summaries into vector store
  - Incremental indexing (only new/changed summaries)
  - Progress indicators
- ✅ `paranoid ask` command:
  - Natural language queries
  - RAG over indexed summaries
  - LLM synthesis of answers
  - Basic relevance ranking
- ✅ `--sources` flag for `ask` command:
  - Lists retrieved sources
  - Shows file paths
  - Displays relevance scores
  - Preview of retrieved content

### In Progress
- ⏳ Enhanced source attribution:
  - Inline citations in answers
  - Source details footer
  - Configurable citation format
- ⏳ Query result refinement:
  - Better relevance scoring
  - Context window optimization
  - Multi-stage retrieval
- ⏳ Index management:
  - `paranoid index --status`
  - Index health checks
  - Repair tools

### Not Started (Phase 5A)
- ❌ Entity-level indexing (moved to Phase 5B)
- ❌ File content chunking and indexing (moved to Phase 5B)
- ❌ Interactive chat mode (moved to Phase 5B/5C)

---

## Implementation Notes

### Key Design Decisions

1. **Distributed Storage**: Each project has its own `.paranoid-coder/` directory
   - Pros: Isolation, portability, no central DB bloat
   - Cons: No cross-project queries (acceptable trade-off)

2. **Bottom-up Tree Walk**: Process files before directories
   - Enables directory summaries to reference child summaries
   - Natural hierarchy for human understanding

3. **Content + Tree Hashing**: Two-level change detection
   - File content hash: Detects file changes
   - Tree hash: Propagates changes up directory hierarchy
   - Enables "what changed?" queries at any level

4. **Lazy Loading in Viewer**: Children loaded on expand
   - Keeps initial load fast
   - Scales to large projects (1000+ files)
   - Smooth user experience

5. **Language-Specific Prompts**: Different prompts per language
   - Better summary quality for language idioms
   - Extensible to new languages
   - Overridable by users

6. **SQLite as Foundation**: Single-file database
   - No server setup required
   - Cross-platform compatibility
   - ACID transactions
   - Good enough for 10k+ summaries

### Performance Observations

- **Hash computation**: ~1-2ms per file on SSD
- **Tree walk**: ~5000 files/sec on typical projects
- **Summarization**: 1-3 files/sec (LLM-bound, expected)
- **Viewer load**: <200ms for 1000 summaries (lazy loading)
- **Database queries**: <5ms for most operations

### Lessons Learned

1. **Mocking Ollama**: Integration tests mock LLM to avoid network dependency
   - Tests are fast and reliable
   - No actual LLM needed in CI/CD
   - Can still test end-to-end flows

2. **Incremental Features**: Ship working subsets, iterate
   - Phase 1 delivered working summarization
   - Viewer added value but wasn't blocking
   - RAG enhances but doesn't replace basic tool

3. **User Feedback**: Dogfooding reveals pain points
   - Stale highlighting was user request
   - `--sources` flag emerged from "where did this come from?" frustration
   - Prompt customization needed for domain-specific code

4. **Test Coverage**: Unit + integration tests catch most bugs
   - Unit tests: Fast, focused, many edge cases
   - Integration tests: Slow, realistic, end-to-end validation
   - Both needed for confidence

---

*This changelog documents completed work. See [project_plan.md](project_plan.md) for active development and roadmap.*
