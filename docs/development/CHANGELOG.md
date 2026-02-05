# Paranoid – CHANGELOG

**Completed development history and implementation notes.**

---

## Phase 5C: Hybrid Ask (Completed)

**Timeline**: 2 weeks  
**Status**: ✅ Complete (query classification + enhanced ask)

### Query Classification (LLM-based)
- ✅ **`paranoid.llm.query_classifier`** – LLM-based query classification (replaces heuristic)
  - Uses small model (`qwen2.5-coder-cpu:1.5b` by default) for fast, robust classification
  - Detects query type: USAGE, DEFINITION, EXPLANATION, GENERATION
  - Entity extraction via regex fallback for graph-backed queries (e.g. "greet", "User.login")
  - Routes: graph (usage/definition), RAG (explanation), RAG+LLM (generation)
  - Fallback to EXPLANATION (RAG path) on classifier/connection errors
- ✅ Config: `default_classifier_model`; CLI: `--classifier-model` for ask
- ✅ `ollama.generate_simple()` for short classification calls (temperature=0, num_predict=10)

### Enhanced `paranoid ask`
- ✅ **Graph-first for usage**: "where is X used?" → direct `get_callers` (instant, no answer LLM)
- ✅ **Graph-first for definition**: "where is X defined?" → `find_definition` (instant, no answer LLM)
- ✅ **RAG for explanation**: "explain X", "how does X work?" → RAG + optional graph context + LLM
- ✅ **RAG for generation**: "write a test", "generate code" → RAG + LLM with generation prompt
- ✅ Fallback to RAG when graph has no results or entity not found
- ✅ `--force-rag` flag to bypass graph routing
- ✅ `--sources` shows graph callers for usage queries, RAG sources for others
- ✅ Storage: `has_graph_data()` to check if code graph exists

### Testing
- ✅ Unit tests for query classifier (`test_query_classifier.py`): parse_category, extract_entity, mocked LLM
- ✅ Integration tests for ask (`test_ask.py`): graph path, definition path, --force-rag, RAG requirements

---

## Phase 5B: Graph-Based Intelligence (Completed)

**Timeline**: 3-4 weeks  
**Status**: ✅ Complete

### Tree-sitter Integration
- ✅ Python parser (classes, functions, methods, imports)
- ✅ JavaScript/JSX parser (classes, functions, methods, imports, export statements)
- ✅ TypeScript/TSX parser (classes, functions, methods, imports, export statements)
- ✅ Extract entities with line numbers, signatures, docstrings
- ✅ Store in `code_entities` table
- ✅ Dependencies: `tree-sitter`, `tree-sitter-python`

### Relationship Extraction
- ✅ Import graph (file-level: `import foo`, `from foo import bar`)
- ✅ Call graph (function/method calls within bodies)
  - Entity-level linking: `from_entity_id` (caller) and `to_entity_id` (callee) when resolvable
  - Parser sets `from_entity_qualified_name` for resolution before storage
- ✅ Inheritance graph (class base classes)
  - Entity-level linking: `from_entity_id` (child class) and `to_entity_id` (base class) when resolvable
- ✅ Store in `code_relationships` table
- ✅ `get_entity_by_qualified_name()` in storage for entity resolution (qualified + simple name fallback)

### `paranoid analyze` Command
- ✅ Walk project tree with tree-sitter
- ✅ Store metadata: `analysis_timestamp`, `analysis_parser_version` (in metadata table)
- ✅ Workflow docs updated: user_manual.md, README.md (Quick start, Common workflows, Commands table)
- ✅ Extract all entities and relationships for supported languages (Python)
- ✅ Incremental updates (delete existing entities per file, re-parse)
- ✅ **Content hash vs. stored hash**: skip unchanged files unless `--force` (schema v4: `analysis_file_hashes` table)
- ✅ Respects ignore patterns (`.paranoidignore`, `.gitignore`)
- ✅ `--force`, `--dry-run`, `-v` flags

### Database Schema (v3, v4)
- ✅ `code_entities` table (file_path, type, name, qualified_name, lineno, docstring, signature, parent_entity_id)
- ✅ `code_relationships` table (from_entity_id, to_entity_id, from_file, to_file, relationship_type, location)
- ✅ `summary_context` table (for future context-rich summarization)
- ✅ `doc_quality` table (for future `paranoid doctor`)
- ✅ `analysis_file_hashes` table (file_path, content_hash) for incremental analyze (v4)
- ✅ Migration runs automatically on init/connect

### Testing
- ✅ Unit tests for parser (`test_analysis_parser.py`):
  - Language support, unsupported language raises
  - Parse file extracts entities (class, function, method) and relationships (imports, calls)
  - Missing file returns empty
  - Docstring extraction

### Context-Rich Summarization (Week 3)
- ✅ **Migrations extracted to dedicated module** (`storage/migrations.py`): schema SQL and migration logic moved out of sqlite.py for clearer structure and easier future schema changes
- ✅ **Graph context injection**: `paranoid summarize` now queries the code graph before calling the LLM when `paranoid analyze` has been run
  - Includes in prompt: imports, exports, callers, callees per entity
  - New storage methods: `get_imports_for_file`, `get_callers_of_entity`, `get_callees_of_entity`
  - New `llm/graph_context.py`: `build_graph_context_for_file()` formats context for LLM
  - Summary `context_level` set to 1 when graph context used, 0 when isolated
  - PROMPT_VERSION bumped to v3

### Smart Invalidation
- ✅ **Track context at summary time**: `compute_file_context_snapshot()` yields imports_hash, callers_count, callees_count
- ✅ **Store in summary_context table**: `set_summary_context` / `get_summary_context` in SQLiteStorage
- ✅ **Re-summarize when content OR context changes**: `needs_summarization()` extended with `_needs_resummary_for_context_change()` when config has smart_invalidation and summary used graph context (context_level=1)
- ✅ **Configurable thresholds**: `smart_invalidation.callers_threshold` (default 3), `callees_threshold` (3), `re_summarize_on_imports_change` (true)

### Context Levels
- ✅ **context_level = 0**: Isolated (no graph, no RAG)
- ✅ **context_level = 1**: With graph context (default when graph available)
- ✅ **context_level = 2**: With RAG context (future; currently same as 1)
- ✅ **--context-level** flag on `paranoid summarize`; config `default_context_level`
- ✅ **Migration**: Ensure context_level column exists; backfill existing summaries to 0

### Viewer (Phase 5B)
- ✅ **Detail panel metadata**: Shows prompt version, context level (Isolated / With graph / With RAG), model version
- ✅ **Needs re-summary flagging**: Tree and detail use `needs_summarization()` (content hash + smart invalidation) instead of simple hash comparison
- ✅ **Status text**: "Needs re-summary (content or context changed)" when item requires re-summarization
- ✅ **Project root passed to DetailWidget** for config (smart invalidation thresholds)

### Graph Query API (Week 4)
- ✅ **`paranoid.graph.GraphQueries`** – high-level graph query API
  - `get_callers(entity)`: Who calls this function/method?
  - `get_callees(entity)`: What does this function/method call?
  - `get_imports(file)`: What does this file import?
  - `get_importers(file)`: What files import this? (module resolution for Python + JS/TS relative imports)
  - `get_inheritance_tree(class)`: Class hierarchy (parents and children)
  - `find_definition(name)`: Locate entity by name
- ✅ **Import resolution**: `_file_path_to_module_name()` derives module name from path; `get_importers` matches Python module names and resolves JS/TS relative imports (./, ../)
- ✅ **Storage extensions**: `get_entity_by_id`, `get_inheritance_parents`, `get_inheritance_children`, `get_entities_matching_name`
- ✅ Unit tests for all graph query methods

### `paranoid doctor` Command (Week 4)
- ✅ **`paranoid doctor [path]`** – scan entities for documentation quality
  - Requires `paranoid analyze` to have been run
  - Scans all entities: has_docstring, has_examples (heuristic), has_type_hints (heuristic)
  - Priority score: (1 + min(callers, 9)) × (1 + min(lines//5, 9)) × (2 if public else 1)
  - Report: missing docstrings, has docstring but no examples, top items by priority
  - `--top N`: show only top N items by priority
  - `--format json`: export to JSON for tooling integration
  - Persists metrics to `doc_quality` table
- ✅ Storage: `get_all_entities(scope_path)`, `set_doc_quality(...)`
- ✅ Integration tests for doctor command

---

## Phase 5A: Basic RAG (Completed)

**Timeline**: 2 weeks  
**Status**: ✅ Complete

### Vector Store & Embeddings
- ✅ sqlite-vec integration
- ✅ Embedding generation for summaries
- ✅ `paranoid index` command:
  - Index summaries into vector store
  - Incremental indexing (only new/changed summaries)
  - Progress indicators

### RAG Query
- ✅ `paranoid ask` command:
  - Natural language queries
  - RAG over indexed summaries
  - LLM synthesis of answers
  - Basic relevance ranking
- ✅ `--sources` flag:
  - Lists retrieved sources
  - Shows file paths
  - Displays relevance scores
  - Preview of retrieved content

### Deferred to Later Phases
- Entity-level indexing → Phase 5B/5C
- File content chunking → Phase 5B/5C

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
- ✅ Stale highlighting (amber background; now uses `needs_summarization` for content + context changes; see Phase 5B Viewer)
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
  - Metadata (model, model version, prompt version, context level, timestamps)
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
