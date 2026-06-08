---
id: TASK-467.4
title: Add end-to-end long-tick regression tests and operator diagnostics
status: Open
assignee: []
created_date: '2026-06-08 18:48'
labels:
  - task
  - tick-latency
  - dispatch-performance
  - 'needs:test'
  - 'needs:docs'
dependencies:
  - TASK-465.3
  - TASK-466.4
  - TASK-467.3
references:
  - oompah/orchestrator.py
  - docs
modified_files:
  - tests/test_orchestrator_handlers.py
  - tests/test_project_pause.py
  - docs
parent_task_id: TASK-467
priority: 0
ordinal: 14
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add tests and documented diagnostics for the long-tick scenario that triggered this work: slow cleanup and maintenance should not prevent a separate eligible Open task from dispatching. Include synthetic slow jobs, multiple projects, dependency-blocked tasks, and one ready task in another workstream.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Regression test reproduces one running agent plus one eligible unrelated Open task while maintenance is slow.
- [ ] #2 Expected behavior dispatches the eligible task without waiting for maintenance completion.
- [ ] #3 Operator-facing diagnostics explain which lane or project is currently slow.
<!-- AC:END -->
