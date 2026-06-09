---
id: TASK-479
title: Push shared epic task metadata before opening rollup PR
status: Done
assignee:
  - oompah
created_date: '2026-06-09 18:32'
updated_date: '2026-06-09 18:43'
labels:
  - bug
dependencies: []
priority: high
ordinal: 207000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Bug: shared epic rollup gating reads child task status from the local shared epic worktree, but _push_epic_branch() only pushes the current branch ref and does not commit dirty Backlog task metadata first. This can open an epic rollup PR while the remote epic branch still records a child as In Progress/Open. Fix the rollup push path to commit shared-worktree Backlog metadata before push and fail closed if non-metadata dirty work remains. Add regression tests.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Changed shared-epic rollup pushes to commit pending Backlog task metadata from the shared epic worktree before pushing HEAD to the epic branch, while keeping stacked mode on named-branch pushes from the project repo. Added regression coverage for shared metadata commits, non-metadata dirty fail-closed behavior, and stacked push behavior. Verified with focused epic strategy tests and full make test.
<!-- SECTION:FINAL_SUMMARY:END -->
