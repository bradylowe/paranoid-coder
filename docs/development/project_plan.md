# Paranoid – Project Plan

**Version:** 1.0  
**Date:** January 2026  
**Status:** Phase 5A Complete; Phase 5B (Graph-Based Intelligence) - In Progress

---

## Executive Summary

**Paranoid** is a privacy-first codebase intelligence tool that helps developers understand, navigate, and analyze complex projects entirely on their local machine. Built on three core principles—**100% local processing**, **distributed storage**, and **intelligent analysis**—Paranoid combines traditional static analysis with LLM-powered semantic understanding to answer questions like "How do I create this deliverable?", "Where is this function used?", and "What needs better documentation?"

**Current Capabilities:**
- **Multi-language summarization**: Generates context-aware summaries of files and directories using local LLMs (via Ollama), with language-specific prompts for Python, JavaScript, TypeScript, Go, Rust, Java, and more
- **Smart change detection**: Content-based and hierarchical tree hashing ensures only modified code is re-analyzed
- **RAG-powered queries**: Natural language questions answered using indexed summaries with source citations (e.g., `paranoid ask "where is authentication handled?" --sources`)
- **Desktop viewer**: PyQt6 GUI for exploring project structure, summaries, and metadata with lazy-loading and search
- **Flexible management**: Commands for stats, export (JSON/CSV), cleaning stale data, and customizing prompts

**Development Focus:**
Transitioning from basic RAG to **hybrid symbolic + semantic architecture**:
- **Graph extraction** (`paranoid analyze`): Build comprehensive code relationship graph (imports, calls, inheritance) using static analysis—fast, deterministic, and zero LLM cost
- **Context-rich summarization**: Single-pass file summaries injected with graph context (imports, callers, usage patterns) to eliminate expensive multi-pass re-summarization
- **Intelligent query routing**: Graph queries for concrete facts ("find all usages"), RAG for semantic search ("explain authentication flow"), LLM synthesis for complex questions
- **Documentation assistant** (`paranoid doctor`): Identify missing/weak docstrings, suggest improvements, prioritize by impact

**Key Differentiators:**
- **Privacy guarantee**: No code or summaries ever leave your machine—all LLM inference, embeddings, and storage are local
- **Distributed architecture**: Each project maintains its own `.paranoid-coder/` SQLite database; no central server, no cross-project interference
- **Efficiency by design**: Graph queries answer 80% of questions instantly without LLM calls; embeddings reserved for semantic search; LLM synthesis only when needed
- **Developer-centric workflow**: Incremental updates, smart invalidation, human-in-the-loop documentation enhancement

**Vision:**
Paranoid aims to become the standard tool for AI-assisted codebase exploration, enabling developers to:
- Onboard to new codebases 10x faster through intelligent summaries and usage examples
- Find bugs, refactoring opportunities, and bottlenecks via hybrid analysis
- Auto-generate tests, documentation, and usage examples based on actual code patterns
- Navigate complex systems through natural language queries backed by deterministic graph analysis

**Technology Stack:**
- **Static analysis**: Tree-sitter (multi-language parsing)
- **LLM**: Ollama (local models like qwen2.5-coder:7b)
- **Storage**: SQLite (summaries, graph, vectors via sqlite-vec)
- **Embeddings**: Local embedding models
- **UI**: PyQt6 desktop viewer + CLI

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Storage Design](#storage-design)
3. [Current Workflow](#current-workflow)
4. [Completed Phases](#completed-phases)
5. [Active Development](#active-development)
6. [Future Roadmap](#future-roadmap)
7. [Technical Specifications](#technical-specifications)

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
│  prompts │ ask │ analyze (5B) │ doctor (5B) │ chat (5B)     │
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
│  - Code entities (classes, functions, methods) [Phase 5B]   │
│  - Code relationships (calls, imports, inheritance) [5B]    │
│  - Vector embeddings (summaries, entities) [Phase 5A/5B]    │
│  - Ignore patterns with timestamps                          │
│  - Generation timestamps                                    │
└─────────────────────────────────────────────────────────────┘
```

### Query Architecture (Phase 5B Goal)

```
┌─────────────────────────────────────────┐
│    User Query (Natural Language)        │
│  "How do I create the PDF report?"      │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
┌──────────────┐    ┌────────────────┐
│ Graph Query  │    │ Vector Search  │
│  (SQLite)    │    │ (Embeddings)   │
│              │    │                │
│ • Usages     │    │ • Summaries    │
│ • Calls      │    │ • Entities     │
│ • Imports    │    │ • Docstrings   │
│ • Inheritance│    │                │
└──────────────┘    └────────────────┘
        │                    │
        └─────────┬──────────┘
                  ▼
        ┌─────────────────┐
        │  Context Builder │
        │  (Combines both) │
        └─────────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │   LLM Synthesis  │
        │  (Final Answer)  │
        └─────────────────┘
```

**Key insight**: Most queries hit the graph first (fast, deterministic), fall back to RAG for semantic search, and use LLM only for synthesis.

---

## Storage Design

### Distributed Local Storage

Each target project gets its own `.paranoid-coder/` directory containing:

```
/path/to/my-project/
├── .paranoid-coder/
│   ├── summaries.db          # SQLite database (primary storage)
│   ├── .paranoid-coder-id    # Project fingerprint (future: for portability)
│   ├── config.json           # Project-specific overrides (optional)
│   └── prompt_overrides.json # Custom prompt templates
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

### Database Schema

**Core Tables (Implemented):**

```sql
-- Primary summaries table
CREATE TABLE summaries (
    path TEXT PRIMARY KEY,
    type TEXT NOT NULL,                 -- 'file' or 'directory'
    hash TEXT NOT NULL,                 -- SHA-256 of file OR tree content
    description TEXT NOT NULL,          -- LLM-generated summary
    file_extension TEXT,
    language TEXT,                      -- 'python', 'javascript', etc.
    error TEXT,
    needs_update BOOLEAN DEFAULT 0,
    
    -- Model metadata
    model TEXT NOT NULL,
    model_version TEXT,
    prompt_version TEXT NOT NULL,
    context_level INTEGER DEFAULT 0,    -- 0 = isolated, future: graph context
    
    -- Timestamps
    generated_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    
    tokens_used INTEGER,
    generation_time_ms INTEGER
);

-- Ignore patterns
CREATE TABLE ignore_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    added_at TIMESTAMP NOT NULL,
    source TEXT                         -- 'file' or 'command'
);

-- Project metadata
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Vector embeddings for RAG (implemented via sqlite-vec)
-- Stores embeddings for summary-level RAG
```

**Phase 5B Extensions:**

```sql
-- Code entities: classes, functions, methods extracted via static analysis
CREATE TABLE code_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,            -- FK to summaries.path
    type TEXT NOT NULL,                 -- 'class', 'function', 'method'
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,       -- e.g., "MyClass.my_method"
    parent_entity_id INTEGER,           -- FK to parent class (for methods)
    
    lineno INTEGER,                     -- Start line number
    end_lineno INTEGER,                 -- End line number
    docstring TEXT,
    signature TEXT,                     -- Function/method signature
    
    language TEXT NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    
    FOREIGN KEY (file_path) REFERENCES summaries(path) ON DELETE CASCADE,
    FOREIGN KEY (parent_entity_id) REFERENCES code_entities(id) ON DELETE CASCADE
);

-- Code relationships: imports, calls, inheritance
CREATE TABLE code_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity_id INTEGER,             -- Source entity (or NULL for file-level)
    to_entity_id INTEGER,               -- Target entity (or NULL for external)
    from_file TEXT,                     -- Source file path
    to_file TEXT,                       -- Target file path (for imports)
    relationship_type TEXT NOT NULL,    -- 'calls', 'imports', 'inherits', 'instantiates'
    location TEXT,                      -- file:line where relationship occurs
    
    created_at TIMESTAMP,
    
    FOREIGN KEY (from_entity_id) REFERENCES code_entities(id) ON DELETE CASCADE,
    FOREIGN KEY (to_entity_id) REFERENCES code_entities(id) ON DELETE CASCADE
);

-- Entity embeddings (separate from summary embeddings)
-- Enables entity-level RAG: "where is User.login?"

-- Summary context tracking (for smart invalidation)
CREATE TABLE summary_context (
    summary_path TEXT PRIMARY KEY,
    imports_hash TEXT,                  -- Hash of import list at summary time
    callers_count INTEGER,              -- Number of callers at summary time
    callees_count INTEGER,              -- Number of callees at summary time
    context_version TEXT,               -- Version of context-building logic
    
    FOREIGN KEY (summary_path) REFERENCES summaries(path)
);

-- Documentation quality metrics
CREATE TABLE doc_quality (
    entity_id INTEGER PRIMARY KEY,
    has_docstring BOOLEAN,
    has_examples BOOLEAN,
    has_type_hints BOOLEAN,
    priority_score INTEGER,             -- Calculated based on usage, complexity
    last_reviewed TIMESTAMP,
    
    FOREIGN KEY (entity_id) REFERENCES code_entities(id)
);
```

---

## Current Workflow

**User workflow (as of Phase 5A):**

```bash
cd /path/to/myproject

# 1. Initialize project (once)
paranoid init .

# 2. Generate summaries
paranoid summarize . --model qwen2.5-coder:7b

# 3. Index for RAG
paranoid index .

# 4. Ask questions
paranoid ask "where is user authentication handled?" --sources

# 5. View in GUI
paranoid view .
```

**Future workflow (Phase 5B):**

```bash
cd /path/to/myproject

# 1. Initialize project (once)
paranoid init .

# 2. Extract code graph (fast, no LLM)
paranoid analyze .

# 3. Generate context-rich summaries (uses graph context)
paranoid summarize . --model qwen2.5-coder:7b

# 4. Index for RAG (summaries + entities)
paranoid index .

# 5. Ask questions (hybrid graph + RAG)
paranoid ask "where is User.login used?" --sources

# 6. Get documentation suggestions
paranoid doctor .

# 7. Interactive chat
paranoid chat
```

---

## Completed Phases

**See [CHANGELOG.md](CHANGELOG.md) for detailed implementation notes.**

### ✅ Phase 1: Core Foundation (Completed)
- SQLite storage backend with migrations
- Content and tree hashing for change detection
- Ignore pattern support (.paranoidignore, .gitignore, built-ins)
- Bottom-up summarization with Ollama integration
- CLI with `init`, `summarize` commands

### ✅ Phase 2: Viewer & User Experience (Completed)
- PyQt6 desktop viewer with lazy-loading tree
- Detail panel, search/filter, context menus
- `view`, `stats`, `export` commands
- Stats include by-language breakdown

### ✅ Phase 3: Maintenance & Cleanup (Completed)
- `clean` command (--pruned, --stale, --model)
- `config` command (--show, --set, --add, --remove, --global)
- Viewer enhancements (show ignored, stale highlighting, re-summarize)
- Comprehensive documentation

### ✅ Phase 4: Multi-Language & Testing (Completed)
- Language detection and language-specific prompts (Python, JS, TS, Go, Rust, Java, Markdown)
- `prompts` command (--list, --edit)
- Prompt override system
- Full unit and integration test suites
- CI/CD with GitHub Actions

### ✅ Phase 5A: Basic RAG (Completed)
- ✅ Vector embeddings (sqlite-vec integration)
- ✅ `paranoid index` command (summary embeddings)
- ✅ `paranoid ask` command (RAG over summaries)
- ✅ `--sources` flag for source attribution

---

## Active Development

### Phase 5B: Graph-Based Intelligence (Next Priority)

**Goal**: Add static analysis foundation to enable deterministic queries and context-rich summarization.

**Target**: 3-4 weeks

#### Week 1-2: Graph Extraction Foundation

- [ ] **Tree-sitter integration**
  - [ ] Python parser (classes, functions, methods, imports)
  - [ ] JavaScript/TypeScript parser
  - [ ] Extract entities with line numbers, signatures, docstrings
  - [ ] Store in `code_entities` table

- [ ] **Relationship extraction**
  - [ ] Import graph (file-level and entity-level)
  - [ ] Call graph (function/method calls)
  - [ ] Inheritance graph (class hierarchies)
  - [ ] Store in `code_relationships` table

- [ ] **`paranoid analyze` command**
  - [ ] Walk project tree with tree-sitter
  - [ ] Extract all entities and relationships
  - [ ] Progress indicators
  - [ ] Incremental updates (only changed files)
  - [ ] Store metadata (analysis timestamp, language, parser version)
  - [ ] Update current workflow docs to incorporate `paranoid analyze .` call

**Deliverable**: `paranoid analyze .` builds complete code graph in seconds.

#### Week 3: Context-Rich Summarization

- [ ] **Graph context injection**
  - [ ] Modify `paranoid summarize` to query graph before calling LLM
  - [ ] Include in prompt: imports, exports, callers, callees
  - [ ] Format context clearly for LLM

- [ ] **Smart invalidation**
  - [ ] Track context at summary time (imports_hash, callers_count)
  - [ ] Store in `summary_context` table
  - [ ] Re-summarize when content OR context changes significantly
  - [ ] Configurable thresholds (e.g., >3 new callers)

- [ ] **Context levels**
  - [ ] `context_level = 0`: Isolated (current behavior)
  - [ ] `context_level = 1`: With graph context (new default)
  - [ ] `context_level = 2`: With RAG context (future)

**Deliverable**: Single-pass summaries that include usage context from graph.

#### Week 4: Graph Queries and Documentation Assistant

- [ ] **Graph query API**
  - [ ] `get_callers(entity)`: Who calls this function/method?
  - [ ] `get_callees(entity)`: What does this function/method call?
  - [ ] `get_importers(file)`: What files import this?
  - [ ] `get_imports(file)`: What does this file import?
  - [ ] `get_inheritance_tree(class)`: Class hierarchy
  - [ ] `find_definition(name)`: Locate entity by name

- [ ] **`paranoid doctor` command**
  - [ ] Scan all entities for documentation quality
  - [ ] Calculate priority scores (usage × complexity × public API)
  - [ ] Generate report: missing docstrings, weak descriptions, no examples
  - [ ] `--top N` flag to show highest-priority items
  - [ ] Export to JSON for tooling integration

- [ ] **Documentation suggestions**
  - [ ] `paranoid suggest-docstring <entity>` (new command or flag)
  - [ ] Use graph to find call sites and tests
  - [ ] Generate docstring draft with examples from usage
  - [ ] User reviews/edits, tool updates entity

**Deliverable**: 
- Graph queries available via API
- `paranoid doctor .` shows documentation gaps with priorities
- Suggested docstrings based on actual usage

### Phase 5C: Hybrid Ask (After 5B)

**Goal**: Integrate graph queries with RAG for intelligent query routing.

**Target**: 2 weeks

- [ ] **Query classification**
  - [ ] Detect query type: usage, definition, explanation, generation
  - [ ] Route to graph (usage/definition), RAG (explanation), LLM (generation)

- [ ] **Enhanced `paranoid ask`**
  - [ ] For "where is X used?": direct graph query (instant)
  - [ ] For "explain X": RAG over summaries + entity docstrings
  - [ ] For "how does X work?": graph context + RAG + LLM synthesis
  - [ ] Combine results intelligently

- [ ] **Entity-level RAG**
  - [ ] Index code entities (signatures, docstrings) separately
  - [ ] Enable queries like "where is User.login?"
  - [ ] Return file:line with code snippet

- [ ] **Interactive chat** (`paranoid chat`)
  - [ ] Multi-turn conversation with history
  - [ ] Commands: `/snippet <entity>`, `/related <entity>`, `/graph <entity>`
  - [ ] Persistent context within session

**Deliverable**: `paranoid ask` intelligently routes queries, uses graph + RAG together.

### Phase 5D: Code Generation (After 5C)

**Goal**: Generate documentation, tests, and code based on project knowledge.

**Target**: 2-3 weeks

- [ ] **README generation**
  - [ ] `paranoid generate readme .`
  - [ ] Use summaries + entity info to describe project structure
  - [ ] Include installation, usage examples from tests

- [ ] **Documentation site**
  - [ ] `paranoid generate docs .`
  - [ ] Per-module docs with API reference
  - [ ] Cross-linking based on graph relationships

- [ ] **Test generation**
  - [ ] `paranoid generate tests <entity>`
  - [ ] Analyze function signature, docstring, existing tests
  - [ ] Generate unit tests with realistic inputs
  - [ ] Coverage-aware (suggest tests for untested code)

- [ ] **Template system**
  - [ ] User-defined generators
  - [ ] Access to full project graph and summaries
  - [ ] Example: generate API client from endpoint definitions

**Deliverable**: Code generation tools backed by deep project understanding.

---

## Future Roadmap

### Phase 6+: Advanced Features (Long-term)

- **MCP Server**: Optional `paranoid mcp-serve`, REST API targeted for agentic use
- **Analysis tools**: Complexity metrics, dependency analysis, bottleneck detection
- **Multi-language support**: Support more languages for project graph
- **Project fingerprinting**: Portable project IDs, Git integration, project remapping
- **Collaboration**: Share summaries, diff summaries, team prompt libraries
- **Web UI**: Optional `paranoid serve`, browser-based viewer, REST API
- **Performance**: Parallel summarization, LRU caching, batch processing
- **IDE integrations**: VS Code extension, JetBrains plugin

---

## Technical Specifications

### Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| Graph extraction | >100 files/sec | Static analysis is fast |
| Hash computation | <5ms per file | Enable fast change detection |
| Tree walk | >1000 files/sec | Keep overhead minimal |
| Database queries | <10ms per lookup | Responsive viewer UI |
| Graph queries | <50ms for most queries | Critical for interactive use |
| Lazy loading | <100ms per node | Smooth tree expansion |
| Summarization | 1-5 files/sec | Depends on LLM speed (acceptable) |
| Storage overhead | <2% of project size | Graph + summaries + embeddings |

### Dependencies

**Core (required):**
- Python 3.10+
- `ollama` (Python client for Ollama API)
- `sqlite3` (built-in)
- `tree-sitter` (static analysis)
- `sqlite-vec` (vector embeddings)

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
  "default_model": "qwen2.5-coder:7b",
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
  },
  "analyze": {
    "enabled_languages": ["python", "javascript", "typescript", "go", "rust"],
    "extract_docstrings": true,
    "extract_signatures": true
  },
  "summarize": {
    "context_level": 1,
    "use_graph_context": true
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
  },
  "summarize": {
    "context_level": 1
  }
}
```

---

## Success Metrics

**Phase 5A Success (Achieved):**
- ✅ Users can ask questions and get relevant answers from summaries
- ✅ Source attribution shows where information came from
- ⏳ Answer quality improvement remains an ongoing goal (e.g. replace manual code search 50% of the time)

**Phase 5B Success (Target):**
- Graph extraction processes 1000+ file project in <10 seconds
- Context-rich summaries reference imports, callers, and usage patterns
- `paranoid doctor` correctly identifies 80%+ of undocumented public APIs
- Graph queries return results in <50ms

**Phase 5C Success (Target):**
- 80% of usage queries answered by graph (no LLM needed)
- Hybrid queries (graph + RAG) more accurate than RAG alone
- Interactive chat maintains context across 10+ turns

**Long-term adoption metrics:**
- GitHub stars: 1000+ (community interest)
- Active users: 500+ (monthly active installations)
- Supported languages: 5+ for graph extraction
- Plugin ecosystem: 10+ community-contributed analyzers

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Tree-sitter complexity | Slow development | Start with Python only, expand incrementally |
| Graph extraction performance | Poor UX on large codebases | Incremental analysis, parallel processing |
| Context injection increases LLM costs | Higher token usage | Make graph context configurable, provide summaries without context |
| Ollama model quality varies | Users get poor summaries | Support multiple models, prompt tuning, quality benchmarks |
| SQLite database corruption | Data loss | Regular backups, repair tools, export functionality |
| Cross-platform compatibility | Windows/Mac users blocked | Test on all platforms, use pathlib |
| LLM hallucinations | Misleading summaries | Disclaimer in UI, versioning for re-summarization |

---

## Development Principles

1. **Privacy first**: All processing stays local, no telemetry, no remote calls
2. **Incremental everything**: Analysis, summarization, indexing should be fast on repeated runs
3. **Graph before LLM**: Use deterministic methods when possible, LLM for synthesis
4. **Human in the loop**: Tools suggest, humans decide (especially for documentation)
5. **Test-driven**: Every feature has unit and integration tests
6. **Dogfood relentlessly**: Use Paranoid to understand Paranoid's codebase

---

## Conclusion

Paranoid is evolving from a **pure RAG tool** to a **hybrid intelligence system** that combines the speed and precision of static analysis with the semantic understanding of LLMs. The roadmap balances ambitious features with practical milestones, always prioritizing privacy, performance, and developer experience.

**Current focus**: 
- Phase 5B (graph extraction and context-rich summarization)

**Next milestones**:
1. Week 1-2: Graph extraction foundation (`paranoid analyze`, tree-sitter, code_entities)
2. Week 3-4: Context-rich summarization and `paranoid doctor`
3. Week 5-6: Integrate graph queries with RAG (Phase 5C)
4. Month 2+: Code generation and advanced features

**Questions or feedback?** Open an issue or discussion on the GitHub repository.

---

*Last updated: January 31, 2026*
