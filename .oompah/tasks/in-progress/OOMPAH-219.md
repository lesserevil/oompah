---
id: OOMPAH-219
type: task
status: In Progress
priority: null
title: Detect shared-worktree commits that absorb another task's changes
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-17T18:24:58.199363Z'
updated_at: '2026-07-17T18:35:53.682727Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: b0882e8f-c580-4c12-b402-9e4cd72a78f0
---
## Summary

Implement persistent reconciliation for shared-epic worktree commit races.

Problem: TRICKLE-45 edited documentation in the shared epic worktree, but could not commit. A later TRICKLE-44 commit on the same shared branch absorbed those edits. TRICKLE-45 then exhausted its incomplete-session limit and moved to Needs Human even though its acceptance work had landed.

Required behavior:
1. When a shared-epic child exits with uncommitted changes or fails the landing gate, persist evidence on the task: shared branch name, observed base SHA, and changed file paths.
2. During normal reconciliation (including after a service restart), inspect commits added to that shared branch after the recorded base SHA.
3. When a later commit touches the recorded paths, add a task comment naming the absorbing commit(s), clear the stale incomplete-session state, and return the task to Open for a fresh verification/closure run. Do not automatically mark the task Done merely from path overlap.
4. Remove or supersede the evidence once the task reaches a terminal state or the verification run completes.
5. Keep non-shared task behavior unchanged and fail open on Git errors.

Tests required:
- Capture records branch, SHA, and paths for a dirty shared worktree.
- Reconciliation after a later matching shared-branch commit reopens the task and writes attribution.
- Unrelated commits do not reopen the task.
- Evidence survives service restart/persistence boundary.
- Terminal tasks and non-shared tasks are ignored.
- Git errors fail open without changing task state.

Acceptance criteria:
- A reproduction equivalent to TRICKLE-45/TRICKLE-44 does not leave the absorbed task in Needs Human.
- Operator-visible task history identifies the absorbing commit and asks a fresh agent to verify/close the task.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

