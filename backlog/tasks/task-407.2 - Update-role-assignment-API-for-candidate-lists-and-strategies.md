---
id: TASK-407.2
title: Update role assignment API for candidate lists and strategies
status: Merged
assignee: []
created_date: '2026-06-01 21:43'
updated_date: '2026-06-03 04:47'
labels:
  - feature
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-407.1
modified_files:
  - oompah/server.py
  - tests/test_providers_role_matrix.py
parent_task_id: TASK-407
priority: high
ordinal: 32000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Change the /api/v1/roles API from one provider/model per role to one strategy plus an ordered candidate list per role.

Current state to inspect first:
- oompah/server.py uses ROLE_MATRIX_KEYS for fast, standard, deep, and default.
- GET /api/v1/roles serializes provider_id and model for each role.
- PUT /api/v1/roles expects provider_id and model for each role and updates all roles atomically.

Required behavior:
- GET returns each role with strategy and candidates.
- PUT accepts strategy and candidates for every role.
- The update must stay atomic: either all roles are valid and saved, or none are changed.
- Keep enough compatibility for existing UI/tests during the transition, such as provider_id/model fields mirroring the first candidate if needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GET /api/v1/roles returns strategy and candidates for fast, standard, deep, and default.
- [x] #2 PUT /api/v1/roles accepts multi-candidate role bodies and persists them.
- [x] #3 PUT rejects an invalid candidate and leaves all existing roles unchanged.
- [x] #4 PUT rejects an invalid strategy.
- [x] #5 Provider and model status information is available for each candidate so the UI can show whether a candidate is usable.
- [x] #6 Existing single-candidate behavior is either supported temporarily or explicitly updated in tests and UI in the same implementation series.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Read the current role API serializer and tests before editing.
2. Extend the role row serializer to include strategy, candidates, and per-candidate provider/model status details.
3. Update PUT validation to require valid strategy and at least one candidate for each role.
4. Reuse RoleStore validation instead of duplicating model/provider rules in server.py.
5. Preserve rollback behavior by snapshotting RoleStore before applying updates.
6. Add tests for valid multi-candidate updates, invalid candidate rollback, old single-candidate request compatibility if retained, and safe GET output.
<!-- SECTION:PLAN:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-02 15:22

TASK-407.2 was reviewed after the Needs Human escalation. The implementation was merged on main in PR #197 (commit 598391d), and the TASK-407.2 worktree full test run passed: 3779 passed, 4 skipped. Marking the source task Done; the Needs Human state was caused by oompah reading the managed checkout instead of the agent worktree closure.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented and merged strategy+candidates support for /api/v1/roles in PR #197. GET now returns strategy and candidates with per-candidate provider/model status. PUT accepts multi-candidate role bodies atomically, preserves legacy provider_id/model compatibility, rejects invalid candidates and invalid strategies, and includes API tests. Verified with make test in the TASK-407.2 worktree: 3779 passed, 4 skipped.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 API tests cover success, validation failure, and rollback behavior.
- [x] #2 No direct edits to backlog task files are needed for this implementation.
<!-- DOD:END -->
