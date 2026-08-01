---
id: OOMPAH-683
type: task
status: Open
priority: null
title: Make retry recovery snapshots tolerate generated hooks and in-progress rebases
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T21:41:35.163259Z'
updated_at: '2026-08-01T21:41:37.434184Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live recovery failures on 2026-08-01 stranded EXOCOMP-145 and OOMPAH-682 because the retry snapshot attempted to stage the generated/ignored .oompah-no-hooks helper, and stranded EXOCOMP-184 because its preserved worktree was detached during an active rebase. In all cases Oompah correctly left the worktree untouched but moved the task to Needs Human, requiring manual reconciliation.

Implementation scope:
- Treat .oompah-no-hooks and all other Oompah-generated worktree helpers as non-deliverable recovery artifacts. Snapshot tracked, staged, and legitimate untracked task work without passing ignored helper paths to git add.
- Detect active rebase/merge/cherry-pick state and detached HEAD before snapshotting. Preserve branch identity, index, operation metadata, and reachable commits without invoking an interactive Git command or losing conflict resolutions.
- If an operation can be safely completed or checkpointed non-interactively, do so through an explicit bounded path; otherwise leave the worktree and branch fully recoverable with precise evidence and no destructive reset.
- Ensure retry cleanup never deletes generated helpers until all task changes are durably reachable, and remove helpers before cleanliness/submission checks.
- Add operator-visible diagnostics that distinguish ignored-helper exclusion, active-operation preservation, and genuine unrecoverable corruption.

Relevant code: orchestrator worker-exit/retry recovery snapshot paths, workspace/project Git helpers, generated hook installation, git_noninteractive policy, and retry tests.

Required tests:
- A dirty task worktree containing ignored .oompah-no-hooks/prepare-commit-msg snapshots successfully without adding the helper.
- A detached HEAD in an active rebase retains the branch/ref, staged conflict resolution, todo state, and commits across recovery.
- A generated helper is absent from submitted branch history and cannot make an otherwise-clean worktree fail submission.
- Late/concurrent retry cleanup cannot overwrite a newer worker generation or remove unsnapshotted changes.
- No recovery path launches an editor or interactive Git command.

Acceptance criteria:
- The EXOCOMP-145/OOMPAH-682 ignored-helper and EXOCOMP-184 detached-rebase reproductions recover automatically without Needs Human or lost work.
- Recovered branches remain pushable and task submission sees the exact intended head.
- Focused recovery/workspace tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

