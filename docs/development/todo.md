# Phase 2: Viewer & User Experience – Todo List

**Source:** [project_plan.md](project_plan.md) Phase 2  
**Target:** 2–3 weeks

**Goal:** Desktop GUI for exploring summaries

**Deliverables:**
- `paranoid view .` launches GUI showing project tree
- User can navigate, search, and inspect summaries
- `paranoid stats .` shows summary metrics
- `paranoid export . --format json` works

---

## 1. PyQt6 viewer application

- [x] Main window with menu bar
- [x] Tree view with lazy loading (fetch children on expand)
- [x] Detail panel showing summary + metadata
- [x] Search/filter widget (by path, content, model)
- [x] Context menu (refresh, re-summarize, copy path)

---

## 2. View command

- [x] Launch viewer from CLI: `paranoid view .`
- [x] Pass project root to viewer
- [x] Handle viewer not installed gracefully

---

## 3. Stats command

- [x] Show summary count by type (files/dirs)
- [x] Coverage percentage (summarized vs. total)
- [x] Last update time
- [x] Model usage breakdown

---

## 4. Export command

- [x] `paranoid export . --format json` → JSON dump
- [x] `paranoid export . --format csv` → Flat CSV
- [x] Optional filtering by path prefix (path argument scopes export, e.g. `paranoid export src/api`)

---

*Last updated: January 2026*
