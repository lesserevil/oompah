---
id: TASK-466
title: 'Epic: move maintenance work off the dispatch critical path'
status: Open
assignee: []
created_date: '2026-06-08 18:47'
updated_date: '2026-06-08 19:00'
labels:
  - epic
  - tick-latency
  - maintenance
  - dispatch-performance
dependencies: []
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests
priority: 0
ordinal: 5
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move slow periodic maintenance out of the serialized tick path so task dispatch is not delayed by cleanup, self-heal, auto-archive, merged-label sweeps, epic rollups, orphan resets, or watchdog scans. Maintenance must remain bounded, idempotent, observable, and safe around git and tracker writes.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Ready task dispatch is not blocked by terminal worktree cleanup or repo self-heal.
- [ ] #2 Maintenance jobs have bounded runtime, backoff, and per-project locking where needed.
- [ ] #3 Existing cleanup, archive, and epic rollup behavior remains covered by tests.
<!-- AC:END -->
