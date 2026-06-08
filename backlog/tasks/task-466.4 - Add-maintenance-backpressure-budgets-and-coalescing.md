---
id: TASK-466.4
title: Add maintenance backpressure budgets and coalescing
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
  - TASK-466.2
  - TASK-466.3
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-466
priority: 0
ordinal: 9
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add scheduling controls so maintenance jobs cannot starve dispatch: per-job minimum interval, max runtime or item budget, in-flight coalescing, skip counters, and explicit next-run timestamps. The scheduler should drop redundant maintenance requests while one is running and should record when a job is skipped because dispatch is busy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A long maintenance job cannot launch duplicate copies of itself.
- [ ] #2 Maintenance jobs enforce configured or hard-coded safety budgets and resume on a later run.
- [ ] #3 State snapshots include enough maintenance lane status to diagnose skipped, running, failed, and completed jobs.
<!-- AC:END -->
