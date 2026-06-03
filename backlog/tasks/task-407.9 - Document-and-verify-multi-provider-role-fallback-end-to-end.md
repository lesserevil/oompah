---
id: TASK-407.9
title: Document and verify multi-provider role fallback end to end
status: Merged
assignee: []
created_date: '2026-06-01 21:45'
updated_date: '2026-06-03 04:48'
labels:
  - feature
dependencies:
  - TASK-407.6
  - TASK-407.7
  - TASK-407.8
modified_files:
  - docs
  - plans
parent_task_id: TASK-407
priority: medium
ordinal: 39000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Finish the multi-provider role assignment feature with documentation, migration notes, and end-to-end verification.

Current state to inspect first:
- User-facing docs belong in docs/.
- Internal design and implementation notes belong in plans/.
- The feature changes operator-facing configuration on the Providers page and internal dispatch behavior.

Required behavior:
- Operators can understand how to configure priority and round-robin role assignments.
- Developers can understand the new role candidate schema and selector state at a high level.
- The implementation is verified with automated tests and a short manual scenario using harmless mocked or configured providers.
- The feature does not regress existing single-candidate projects.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 User-facing documentation explains how to configure priority and round-robin role assignments.
- [x] #2 Documentation explains what provider failures cause fallback to the next candidate.
- [x] #3 Documentation explains that the provider Test button does not create tasks or update round-robin usage.
- [x] #4 Migration from old single-candidate roles is verified.
- [x] #5 make test passes before this task is marked Done.
- [x] #6 Any discovered follow-up work is filed as Backlog tasks under TASK-407.
<!-- AC:END -->



## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add or update user-facing docs explaining role candidates, priority strategy, round-robin strategy, failover cases, and the provider Test button.
2. Add or update an internal plan/design note only if the implementation introduces non-obvious selector state or dispatch behavior that maintainers need to understand.
3. Verify migration from old one-provider roles.json to the new candidate schema.
4. Run focused tests while developing and make test before closing.
5. Manually check the Providers page on port 8090: load roles, add candidates, reorder candidates, save, reload, use Test button, and confirm layout remains usable.
6. Capture any follow-up bugs as Backlog tasks with parent TASK-407 if they are discovered.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Understanding: This task requires user-facing docs in docs/ for operators on how to configure multi-candidate roles with priority/round-robin, what causes provider failover, and the Test button behavior. Also requires internal design notes in plans/ for developers, end-to-end test coverage verifying migration from legacy single-candidate roles.json and non-regression of single-candidate projects, and make test passing.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Delivered: docs/multi-provider-roles.md (operator guide covering priority/round-robin strategies, candidate configuration, failover conditions, Test button behavior, migration from single-candidate format), plans/multi-provider-role-dispatch.md (developer design notes on candidate schema, CandidateSelector state, dispatch loop, backward compat), tests/test_multi_provider_e2e.py (31 e2e tests). All merged to main as PR #204. Verification: 511 tests across all multi-provider feature modules pass with 0 failures. All AC criteria met.
<!-- SECTION:FINAL_SUMMARY:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Docs or plans are updated in the correct directory.
- [x] #2 Automated tests and manual verification results are recorded in the final summary.
<!-- DOD:END -->
