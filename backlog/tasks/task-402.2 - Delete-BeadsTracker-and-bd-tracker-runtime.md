---
id: TASK-402.2
title: Delete BeadsTracker and bd tracker runtime
status: Open
assignee: []
created_date: '2026-06-01 19:20'
updated_date: '2026-06-01 19:20'
labels:
  - task
dependencies:
  - TASK-402.1
parent_task_id: TASK-402
priority: high
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove the Beads tracker backend and all direct bd CLI tracker operations from runtime code.

Context:
- oompah/tracker.py currently contains both BeadsTracker and BacklogMdTracker.
- After this epic, oompah must not have a runtime tracker implementation backed by bd.
- Historical migrated frontmatter such as beads.id may remain in old task files, but it must not imply runtime Beads support.

Work required:
- Delete BeadsTracker or reduce it to removed-code history; runtime imports must no longer reference it.
- Update orchestrator tracker creation so it always creates BacklogMdTracker for the main repo and every project repo.
- Remove type unions and comments that describe Beads as a live backend.
- Update generic tracker errors/docstrings so they are not bd-specific.
- Remove or rewrite tests that instantiate BeadsTracker.

Files to inspect first:
- oompah/tracker.py
- oompah/orchestrator.py
- oompah/error_watcher.py
- tests/test_tracker.py
- tests/test_backlog_tracker.py
- tests/test_error_watcher.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No production code imports or instantiates BeadsTracker.
- [ ] #2 No production tracker path shells out to bd.
- [ ] #3 Tracker tests cover BacklogMdTracker as the sole backend.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Locate every BeadsTracker import and instantiation.
2. Replace tracker factory/type hints with BacklogMdTracker.
3. Remove bd subprocess helpers and Beads-specific error normalization from tracker runtime.
4. Rewrite tests to use BacklogMdTracker or delete tests that only covered bd behavior.
5. Run focused tracker/orchestrator tests.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 rg 'BeadsTracker|_run_bd|bd command' oompah tests returns no runtime references except intentionally retained historical text.
- [ ] #2 Focused tracker tests pass.
<!-- DOD:END -->
