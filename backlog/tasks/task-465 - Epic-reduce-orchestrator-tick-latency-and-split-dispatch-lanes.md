---
id: TASK-465
title: 'Epic: reduce orchestrator tick latency and split dispatch lanes'
status: Backlog
assignee: []
created_date: '2026-06-08 18:47'
labels:
  - epic
  - tick-latency
  - dispatch-performance
dependencies: []
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests
priority: 0
ordinal: 1
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Long orchestrator ticks are delaying dispatch and making the dashboard feel stale. Split the current monolithic tick into a fast serialized dispatch lane and separate bounded maintenance lanes, while preserving correctness for shared state, tracker writes, git worktrees, YOLO review handling, and auto-update.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A full tick no longer blocks eligible task dispatch behind non-critical maintenance sweeps.
- [ ] #2 Dispatch remains single-owner for candidate claiming and agent startup.
- [ ] #3 The UI exposes enough timing information to identify the slow substep when a tick exceeds the slow threshold.
<!-- AC:END -->
