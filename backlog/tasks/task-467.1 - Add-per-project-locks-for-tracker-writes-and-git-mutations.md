---
id: TASK-467.1
title: Add per-project locks for tracker writes and git mutations
status: Open
assignee: []
created_date: '2026-06-08 18:48'
labels:
  - task
  - tick-latency
  - dispatch-performance
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-465.2
references:
  - oompah/orchestrator.py
  - oompah/projects.py
modified_files:
  - oompah/orchestrator.py
  - oompah/projects.py
  - tests/test_submit_queue_concurrency.py
parent_task_id: TASK-467
priority: 0
ordinal: 11
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Introduce explicit per-project and, where needed, per-epic locks for operations that mutate Backlog task files, GitHub tracker state, git worktrees, branches, or review metadata. Use the locks from dispatch, maintenance, YOLO, epic rollup, self-heal, and worker-exit paths so background parallelism cannot corrupt shared state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tracker writes for the same project are serialized through a single lock.
- [ ] #2 Git worktree and branch mutations for the same project cannot overlap unsafely.
- [ ] #3 Tests cover concurrent maintenance plus dispatch attempts on the same project.
<!-- AC:END -->
