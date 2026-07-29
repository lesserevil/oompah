---
id: OOMPAH-556
type: feature
status: Backlog
priority: 0
title: Allocate isolated private branches for epic children
parent: OOMPAH-555
children: []
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:21.738821Z'
updated_at: '2026-07-29T16:24:22.348985Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Replace shared child workspace allocation under parallel mode with one worktree and branch per child, named without Git ref namespace collisions and based on the latest epic integration head. Persist private branch identity separately from the epic delivery branch. Keep epic repair agents on the epic branch. Add drain-time migration rules for existing Open, In Progress, Ready, and Done children and reject unsafe mixed shared/private dispatch.

Tests must cover concurrent workspace creation, branch naming, latest-main/epic bases, nested epics, tracker persistence, existing shared worktree migration, dirty worktrees, crash recovery, and no cross-worktree writes.

Acceptance criteria: concurrent children never share a worktree or checked-out branch, existing work is preserved, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:24
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
<!-- COMMENTS:END -->
