---
id: OOMPAH-578
type: task
status: Backlog
priority: null
title: Prune terminal worktrees that use the legacy epic-task branch shape
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T03:38:06.370836Z'
updated_at: '2026-07-30T03:38:06.370836Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: Extend OOMPAH-561 terminal cleanup compatibility for legacy task records whose exact Oompah-owned worktree/branch is named epic-<task-identifier> even though the tracker record type is task. Treat only the exact same-identifier legacy shape as owned; continue rejecting shared parent epic branches and arbitrary metadata. Remove the matching epic-named worktree before deleting its local/remote branch. Relevant code: oompah/projects.py and tests/test_projects.py (plus orchestrator cleanup tests if needed). Tests: reproduce an Archived task with work_branch=epic-TASK-42 and epic-TASK-42 worktree, prove worktree/local/remote cleanup; prove epic-TASK-EPIC for child TASK-42 remains protected; run focused project/orchestrator cleanup tests and the configured full gate. Acceptance criteria: legacy terminal Oompah workspaces are pruned on the normal 60-second cleanup cadence, exact ownership checks remain fail-closed, and active/shared/unmerged work is preserved.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

