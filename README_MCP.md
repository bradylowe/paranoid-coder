# Paranoid MCP Server – Agent Documentation

**Local-only codebase summarization and analysis.** This MCP server exposes Paranoid tools for AI agents (Cursor, Claude Code, etc.). No code or summaries leave the machine.

## Setup

The user configures `paranoid-mcp` in their MCP client (e.g. Cursor). Command: `paranoid-mcp`. Requires `pip install -e ".[mcp]"` for the host.

## Path handling

**All tools (except `paranoid_job_status`) require `project_path` explicitly.** No default (e.g. cwd). Pass absolute or relative path; it is normalized before use.

```text
paranoid_stats(project_path="/path/to/project")
paranoid_ask(project_path="/path/to/project", question="where is auth handled?")
```

## Readiness flow

**Call `paranoid_readiness(project_path)` first** to see what the project needs:

```json
{
  "initialized": true,
  "has_graph": true,
  "has_summaries": true,
  "has_index": true,
  "next_steps": [],
  "ready_for_ask": true,
  "ready_for_doctor": true,
  "ready_for_find_usages": true,
  "ready_for_find_definition": true
}
```

If `next_steps` is non-empty, run those tools in order before others:
- `paranoid_init` — create project
- `paranoid_analyze` — extract code graph (fast, no LLM)
- `paranoid_summarize` — generate summaries (long-running; async)
- `paranoid_index` — build RAG index (long-running; async)

## Tools

| Tool | When to use |
|------|-------------|
| `paranoid_readiness` | Assess what to run; call first |
| `paranoid_init` | Create project (idempotent) |
| `paranoid_analyze` | Extract code graph (no LLM) |
| `paranoid_summarize` | Generate summaries (async) |
| `paranoid_index` | Build RAG index (async) |
| `paranoid_job_status` | Poll summarize/index completion |
| `paranoid_stats` | Coverage, language breakdown, last update |
| `paranoid_ask` | Question over codebase (graph + RAG + LLM) |
| `paranoid_doctor` | Doc quality report (requires analyze) |
| `paranoid_find_usages` | "Where is X called?" (graph-only, instant) |
| `paranoid_find_definition` | "Where is X defined?" (graph-only, instant) |

## Structured errors

Errors return JSON with `error`, `message`, `remedy`, and `next_steps`:

```json
{
  "error": "Project not initialized",
  "message": "No paranoid project found. Run paranoid_init first.",
  "remedy": "paranoid_init",
  "next_steps": ["paranoid_init"]
}
```

If a tool fails, run `remedy` or the tools in `next_steps`. For generic failures, call `paranoid_readiness` to assess.

## Long-running commands (summarize, index)

`paranoid_summarize` and `paranoid_index` return immediately with a `job_id`:

```json
{
  "job_id": "abc-123",
  "status": "running",
  "command": "summarize",
  "project_path": "/path/to/project",
  "polling": "Call paranoid_job_status(job_id) to check completion..."
}
```

**Polling:** Call `paranoid_job_status(job_id)` every 5–10 seconds. When `status` is `completed` or `failed`, the job is done. Alternatively, poll `paranoid_stats(project_path)` to detect progress (summary count, last_updated change).

For very long runs (hours), the job registry is in-memory and lost on server restart. Suggest the user run the CLI directly.

## Typical workflow

1. `paranoid_readiness(project_path)` — check state
2. If `next_steps` has items: run `paranoid_init`, `paranoid_analyze`, `paranoid_summarize`, `paranoid_index` as needed
3. For summarize/index: poll `paranoid_job_status(job_id)` until done
4. Then: `paranoid_ask`, `paranoid_doctor`, `paranoid_find_usages`, `paranoid_find_definition`, `paranoid_stats`, etc.

## Graph tools (require analyze)

`paranoid_find_usages` and `paranoid_find_definition` require `paranoid_analyze` first. They return:
- **find_usages:** `callers` list with `qualified_name`, `file_path`, `location`
- **find_definition:** `definitions` list with `file_path`, `lineno`, `signature`, `docstring_preview`

Use qualified names: `"User.login"`, `"greet"`.
