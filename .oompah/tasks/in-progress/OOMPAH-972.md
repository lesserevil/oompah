---
id: OOMPAH-972
type: task
status: In Progress
priority: null
title: Repair stale editable installs after worktree retirement
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T20:03:49.482603Z'
updated_at: '2026-08-09T20:24:54.522248Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Aggressive cleanup of merged OOMPAH worktrees exposed a deterministic local-environment bug: the main checkout .venv retained an editable-install .pth pointing at the retired /home/shedwards/src/oompah-967 worktree, while .venv/.uv-setup remained newer than pyproject.toml. Consequently make setup was a no-op and .venv/bin/oompah failed with ModuleNotFoundError until the setup stamp was manually invalidated. Implementation scope: make the setup target validate that the installed oompah package resolves to the current checkout before accepting the idempotency stamp, and reinstall when the editable target is absent or belongs to another worktree; preserve trusted task-private venv checks and normal fast idempotent setup. Relevant files: Makefile/setup helpers and focused setup/install tests. Required tests: reproduce a stale editable target with a fresh setup stamp, prove make setup repairs it to the invoking checkout, prove an already-correct install remains idempotent, and prove task-private interpreter/symlink fail-closed checks remain intact. Acceptance: merged-worktree pruning cannot leave the main oompah CLI unusable, focused tests and protected Python 3.11/3.12/3.13 CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 20:04
---
Accepted for direct-owner repair during the aggressive branch/worktree pruning completion pass; reproduced locally and restored the current CLI only by invalidating the stale setup stamp.
---
author: oompah
created: 2026-08-09 20:24
---
Implementation complete at exact rebased head 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e on main a7c418ee4. Setup now validates the private venv and isolated editable source even with a fresh stamp, refreshes stale worktree targets, preserves the correct-install fast path, and fails before stamp mutation when uv partially updates metadata then exits nonzero. Evidence: 46 focused setup/lifecycle tests, real first-run and repeated idempotent make setup/test-setup, secret scan, diff check, and independent review. Review found and the final commit closed the partial-installer fail-open; narrow re-review passed 3 nodes and full setup module passed 18 with no remaining blocker.
---
<!-- COMMENTS:END -->
