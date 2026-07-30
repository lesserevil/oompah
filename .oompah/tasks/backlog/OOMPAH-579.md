---
id: OOMPAH-579
type: task
status: Backlog
priority: null
title: Prune branchless terminal legacy epic-task worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:54:54.485192Z'
updated_at: '2026-07-30T03:54:54.485192Z'
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

