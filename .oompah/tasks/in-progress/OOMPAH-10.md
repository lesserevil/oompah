---
id: OOMPAH-10
type: bug
status: In Progress
priority: 1
title: Fix native markdown tracker default-branch sync failures
parent: null
children: []
blocked_by: []
labels:
- bug
- native-tracker
- dispatch
- git-sync
assignee: null
created_at: '2026-06-20T02:43:17.381453Z'
updated_at: '2026-06-20T02:45:29.437704Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e11e3b9d-d625-45d0-b56e-65b58d4f37d0
---
## Summary

The native markdown tracker dispatch path can fail before launching an agent when it tries to update task state with `git pull --rebase origin main`. In the managed trickle repo this reproduced on a clean default branch with:

```
git pull --rebase origin main
fatal: Cannot rebase onto multiple branches
```

This prevented TRICKLE-2 from being marked In Progress and aborted dispatch, leaving no agents running until a later retry happened to get past the sync step.

Expected behavior:
- Syncing native `.oompah/tasks` on the managed default branch should be robust for clean fast-forward cases.
- Use an explicit fetch plus safe fast-forward/update strategy instead of a brittle `git pull --rebase origin main` for tracker metadata commits.
- If sync cannot proceed, oompah should surface a clear alert with the project, task, command, and remediation path instead of silently starving dispatch.

Acceptance criteria:
- Reproduce the failure with a unit or integration test around the native markdown tracker/project sync path.
- Replace the failing rebase pull path with deterministic fetch/fast-forward behavior for clean managed default branches.
- Preserve protection for dirty/conflicted worktrees; do not overwrite user work.
- Dispatch no longer aborts for a clean up-to-date managed repo due to `Cannot rebase onto multiple branches`.
- A failed sync creates a visible actionable alert.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

