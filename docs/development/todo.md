# Phase 3: Maintenance & Cleanup – Todo List

**Source:** [project_plan.md](project_plan.md) Phase 3  
**Target:** 2 weeks

**Goal:** Tools for managing summary lifecycle

**Deliverables:**
- `paranoid clean` with multiple modes
- `paranoid config` for settings management
- Comprehensive user documentation

---

## 1. Clean command

- [x] `paranoid clean --pruned` removes summaries for ignored paths
- [x] `paranoid clean --stale --days 30` removes old summaries
- [x] `paranoid clean --model old-model` removes specific model's summaries
- [x] Dry-run mode to preview deletions
- [x] Scope clean to subpath (e.g. `paranoid clean ./subdir --model x` only affects summaries under `subdir`)

---

## 2. Config command

- [x] `paranoid config --show` displays current settings
- [x] `paranoid config --set key=value` for overrides
- [x] `paranoid config --add key=value` for adding items to lists
- [x] `paranoid config --remove key=value` for removing items from lists
- [x] Support for project-local `.paranoid-coder/config.json`
- [x] Support for global `~/.paranoid/config.json` via `--global` flag

---

## 3. Viewer enhancements

- [ ] Show/hide ignored paths (checkbox)
- [ ] Highlight stale summaries (hash mismatch)
- [ ] "Refresh" action to re-compute hashes
- [ ] "Re-summarize" action for selected items

---

## 4. Documentation

- [ ] User guide: installation, quickstart, configuration
- [ ] Examples: `.paranoidignore` patterns, common workflows
- [ ] Troubleshooting: Ollama connection, performance

---

*Last updated: January 2026*
