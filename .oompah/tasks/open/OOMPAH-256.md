---
id: OOMPAH-256
type: task
status: Open
priority: null
title: Make the native Markdown tracker read and write the configured state branch
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-255
labels: []
assignee: null
created_at: '2026-07-20T16:29:29.498883Z'
updated_at: '2026-07-20T16:31:19.440831Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Scope

Extend the native Markdown tracker so a project configured with a state branch reads task files from that branch and commits task mutations only there. Code repository operations, PR branches, main, and release branches must remain independent. Preserve the legacy default-branch tracker behavior when no state branch is configured.

Implementation requirements

- Create or reuse a safe dedicated Git worktree or equivalent branch-scoped repository access for the configured state branch; do not switch the shared code checkout between branches.
- Initialize a missing configured state branch only through the explicit bootstrap or migration flow. Normal reads must not create remote branches.
- Route all tracker reads, task writes, comments, status changes, dependencies, and task discovery through the state-branch worktree after migration.
- Keep project code Git operations and state-branch writes isolated with clear locks and error handling.
- Implement pull/rebase/push conflict recovery that never uses destructive reset and provides an actionable error when recovery is impossible.

Tests

- Integration fixture with distinct main and oompah/state branches proves tracker reads and writes use state while code main remains byte-for-byte unchanged.
- Legacy fixture without state-branch configuration proves existing behavior is unchanged.
- Concurrency test covers simultaneous code fetch/rebase activity and a tracker write.
- Failure tests cover missing branch, authentication failure, and non-fast-forward state-branch push without corrupting task data.

Acceptance criteria

- Task mutations for a migrated project create commits only on its configured state branch.
- Code branch heads are not changed by normal native tracker operations.
- Legacy projects continue to work without migration.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

