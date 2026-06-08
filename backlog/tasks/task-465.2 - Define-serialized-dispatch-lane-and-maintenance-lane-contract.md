---
id: TASK-465.2
title: Define serialized dispatch lane and maintenance lane contract
status: Open
assignee: []
created_date: '2026-06-08 18:47'
labels:
  - task
  - tick-latency
  - dispatch-performance
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-465.1
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-465
priority: 0
ordinal: 3
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Design and implement the scheduling contract that keeps candidate claiming and agent startup serialized while allowing non-critical maintenance work to run on separate bounded lanes. Introduce explicit lane names, ownership rules for shared mutable state, and a single place where tick events are coalesced into dispatch work versus maintenance work.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Candidate selection, issue claiming, and _dispatch() remain single-owner and cannot run concurrently with another dispatch selection pass.
- [ ] #2 Maintenance jobs have explicit lane names and do not block the dispatch lane except where their outputs are required for correctness.
- [ ] #3 Repeated tick requests coalesce instead of piling up unbounded full-tick work.
<!-- AC:END -->
