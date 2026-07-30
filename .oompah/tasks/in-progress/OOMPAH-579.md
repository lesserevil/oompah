---
id: OOMPAH-579
type: task
status: In Progress
priority: null
title: Prune branchless terminal legacy epic-task worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:54:54.485192Z'
updated_at: '2026-07-30T03:55:12.697675Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by live verification of OOMPAH-578. Implementation scope: when a Merged/Archived non-epic task has no work_branch metadata, detect the old Oompah layout only if its exact managed epic-<same-task-identifier> worktree directory exists; use that exact branch/worktree as the cleanup candidate. Do not infer arbitrary branches, shared parent epic branches, or unregistered paths. Relevant code: oompah/projects.py and tests/test_projects.py. Tests: run the real bare-remote legacy cleanup scenario both with explicit legacy branch metadata and with branch_name omitted; prove worktree/local/remote refs are removed, while shared-parent and arbitrary branches remain rejected. Acceptance criteria: archived OOMPAH-310-style workspaces are pruned on the normal cleanup pass without widening ownership beyond exact managed same-identifier paths; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 03:55
---
Live reproduction confirmed OOMPAH-310 is Archived with work_branch unset while its exact managed epic-OOMPAH-310 worktree and branch remain. Implemented same-identifier managed-path fallback only; testing explicit and absent metadata paths against a real bare remote.
---
<!-- COMMENTS:END -->
