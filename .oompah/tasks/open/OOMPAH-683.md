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
updated_at: '2026-08-01T21:45:44.314584Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3114887b63299d36a0155e1dc831ca696d01549ed766eaa53b8d839fe5273e51
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 84374209-87c8-45c2-9ada-2246443044c4
  claim_owner: 9c8dda42-c87b-429a-bdb1-42da8ebebe7e
  claimed_at: '2026-08-01T21:45:35.886090+00:00'
  claim_expires_at: '2026-08-01T22:15:35.886090+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: cc2c91c8-f6ff-417b-ac0e-a5a7e10ee91c
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 21:45
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 21:45
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
