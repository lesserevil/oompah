---
id: TASK-464.2
title: Implement legacy Backlog dual-read and dispatch flags
status: In Progress
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 03:38'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-464.1
  - TASK-461.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - tests
parent_task_id: TASK-464
priority: high
ordinal: 159000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement legacy_backlog_enabled and legacy_backlog_dispatch semantics. Existing Backlog tasks may remain visible or dispatchable by explicit project setting, but all new tasks and follow-ups should use GitHub Issues after cutover.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Legacy Backlog tasks can be visible without being dispatchable.
- [ ] #2 Follow-up tasks from legacy runs go to GitHub unless explicitly configured otherwise.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 03:18
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 03:20
---
UNDERSTANDING: Confirmed this is NOT a duplicate. Searched for legacy_backlog_enabled, legacy_backlog_dispatch, dual-read semantics — no other task covers this specific behavior. Closest related: TASK-459.3 (adds model fields, Open), TASK-460.3 (follow-up routing, Backlog), TASK-461.1 (tracker registry, Backlog). TASK-464.2 uniquely implements the orchestrator/dispatch behavioral semantics: (1) legacy_backlog_enabled gate — Backlog tasks visible but not dispatchable unless legacy_backlog_dispatch is also true, (2) follow-up tasks go to GitHub unless explicitly overridden. Plan: add legacy_backlog_enabled and legacy_backlog_dispatch fields to Project model (TASK-459.3 is Open so I'll add minimal fields here), then gate dispatch in orchestrator, and route follow-up task creation through GitHub by default.
---

author: oompah
created: 2026-06-10 03:25
---
DISCOVERY: Key code locations confirmed. Project model (oompah/models.py:line 324-334) has tracker_kind but NOT yet legacy_backlog_enabled/legacy_backlog_dispatch — the NOTE says TASK-459.3 will add them. Since TASK-459.3 is Open (not done), I'll add the fields here as part of this task's scope. Key dispatch gate is _should_dispatch() in oompah/orchestrator.py:4776+. Visibility gate is _fetch_all_issues() in oompah/server.py:1801+. Issue.tracker_kind is None for Backlog issues (BacklogMdTracker never sets it). _is_github_backed() helper exists in oompah/projects.py. UPDATABLE_FIELDS in projects.py needs the new flags added. Plan: (1) add fields to Project model, (2) update to_dict/from_dict, (3) add to UPDATABLE_FIELDS, (4) add dispatch gate in _should_dispatch, (5) add visibility filter note in _fetch_all_issues, (6) write comprehensive tests.
---

author: oompah
created: 2026-06-10 03:38
---
IMPLEMENTATION: Added legacy_backlog_enabled and legacy_backlog_dispatch fields to Project model (oompah/models.py). (1) Both default to False, emitted only when True in to_dict() to keep records compact. (2) from_dict() parses them with False defaults so existing project records round-trip safely. (3) Added both + tracker_kind to ProjectStore.UPDATABLE_FIELDS (oompah/projects.py). (4) In _should_dispatch() (orchestrator.py): GitHub-backed projects now reject Backlog issues (tracker_kind not in github_issues/github-issues) with reason 'legacy_backlog_not_dispatchable' unless project.legacy_backlog_dispatch=True. Non-GitHub projects and issues without project_id are unaffected. (5) In _fetch_all_candidates() (orchestrator.py): GitHub-backed projects filter out Backlog issues when legacy_backlog_enabled=False; tag them as tracker_kind='backlog_md' when enabled=True. (6) Same dual-read filter added to _fetch_all_issues() in server.py for dashboard visibility. Updated existing UPDATABLE_FIELDS test in test_projects_crud.py.
---

author: oompah
created: 2026-06-10 03:38
---
VERIFICATION: 32 new tests all pass. Full sweep of related tests: 251 tests pass (test_models, test_projects, test_projects_crud, test_backlog_hook_tracker_guards, test_project_pause, test_legacy_backlog_dispatch). Additional dispatch gate tests: 183 pass (test_backlog_conflict, test_dispatch_event_loop, test_dispatch_close_race, test_default_first_dispatch). 49 budget/dispatch tests pass. No regressions detected.
---
<!-- COMMENTS:END -->
