---
id: TASK-465.3
title: Add regression coverage for tick lane serialization
status: Open
assignee: []
created_date: '2026-06-08 18:47'
labels:
  - task
  - tick-latency
  - dispatch-performance
  - 'needs:test'
dependencies:
  - TASK-465.2
references:
  - oompah/orchestrator.py
modified_files:
  - tests/test_orchestrator_handlers.py
  - tests/test_submit_queue_concurrency.py
parent_task_id: TASK-465
priority: 0
ordinal: 4
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add tests that prove full ticks do not overlap unsafely, dispatch selection is serialized, maintenance work can run without blocking eligible dispatch, and tick requests raised while maintenance is active are coalesced into the next safe dispatch pass.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A slow maintenance job does not prevent a ready Open task from being dispatched on the dispatch lane.
- [ ] #2 Two dispatch selection passes cannot claim the same issue.
- [ ] #3 Tests cover shutdown/restart behavior with maintenance jobs in flight.
<!-- AC:END -->
