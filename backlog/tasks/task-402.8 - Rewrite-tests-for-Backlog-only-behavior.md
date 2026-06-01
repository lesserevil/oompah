---
id: TASK-402.8
title: Rewrite tests for Backlog-only behavior
status: Open
assignee: []
created_date: '2026-06-01 19:20'
updated_date: '2026-06-01 19:21'
labels:
  - task
dependencies:
  - TASK-402.7
parent_task_id: TASK-402
priority: high
ordinal: 20000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Rewrite and consolidate tests for Backlog-only behavior after Beads removal and status migration.

Context:
- Many current tests exercise BeadsTracker, bd command error handling, .beads project setup, and legacy four-state dashboard behavior.
- Each implementation task should update tests for its own changes, but this task is the final cross-suite cleanup to ensure no stale Beads assumptions remain.

Work required:
- Delete tests that only cover removed Beads behavior.
- Rewrite tests that should now cover Backlog.md equivalents.
- Add integration-style tests for Backlog-only project creation, tracker construction, status transitions, dispatch gating, dashboard serialization, and merge-to-Merged behavior.
- Ensure test fixtures use Backlog task markdown files and Backlog config, not bd JSON.
- Run make test and fix failures caused by stale assumptions.

Files to inspect first:
- tests/test_tracker.py
- tests/test_backlog_tracker.py
- tests/test_projects.py
- tests/test_beads_to_backlog.py
- tests/test_beads_merge_driver.py
- tests/test_dashboard_hide_merged.py
- tests/test_orchestrator_merged.py
- tests/test_asking_questions.py
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The test suite has no dependency on BeadsTracker, bd, BEADS_DIR, or .beads fixtures.
- [ ] #2 Backlog-only tracker construction and lifecycle statuses are covered by tests.
- [ ] #3 make test passes.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Run rg for BeadsTracker, bd, .beads, BEADS_DIR, and legacy dashboard states in tests.
2. Delete obsolete test files only after production code no longer imports those modules.
3. Add Backlog-only regression coverage for every removed Beads behavior that still has a Backlog equivalent.
4. Run focused tests repeatedly while cleaning up.
5. Finish with make test.
<!-- SECTION:PLAN:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Obsolete Beads tests are deleted or rewritten.
- [ ] #2 Full test output is summarized in the final task comment.
<!-- DOD:END -->
