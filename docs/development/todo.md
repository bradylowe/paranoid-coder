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

- [ ] `paranoid clean --pruned` removes summaries for ignored paths
- [ ] `paranoid clean --stale --days 30` removes old summaries
- [ ] `paranoid clean --model old-model` removes specific model's summaries
- [ ] Dry-run mode to preview deletions

---

## 2. Config command

- [ ] `paranoid config --show` displays current settings
- [ ] `paranoid config --set key=value` for overrides
- [ ] Support for project-local `.paranoid-coder/config.json`

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
