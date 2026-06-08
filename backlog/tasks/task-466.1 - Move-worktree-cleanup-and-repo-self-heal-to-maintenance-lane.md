---
id: TASK-466.1
title: Move worktree cleanup and repo self-heal to maintenance lane
status: Open
assignee: []
created_date: '2026-06-08 18:48'
labels:
  - task
  - tick-latency
  - maintenance
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-465.2
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-466
priority: 0
ordinal: 6
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Run terminal worktree cleanup and managed checkout self-heal as scheduled maintenance jobs instead of inline work in the full dispatch tick. Preserve the rule that only merged and archived worktrees are removed, keep done/conflict worktrees intact, and expose job status in tick diagnostics.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Terminal worktree cleanup no longer contributes to dispatch tick latency.
- [ ] #2 Done worktrees are not deleted unless the task is also merged or archived.
- [ ] #3 Repo self-heal remains automatic and reports failures without blocking dispatch.
<!-- AC:END -->
