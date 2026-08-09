---
id: OOMPAH-977
type: task
status: In Validation
priority: null
title: Keep managed worktree hook paths worktree-local
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T22:45:47.293153Z'
updated_at: '2026-08-09T23:11:34.041678Z'
work_branch: OOMPAH-977
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-977
  head_sha: f8467e42bad3c7db6d47678539ec62fc852e464e
  submitted_at: '2026-08-09T23:00:43.743463+00:00'
  updated_at: '2026-08-09T23:00:43.743463+00:00'
oompah.work_branch: OOMPAH-977
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-1b8d08d9006f
    project_id: proj-14849f1b
    task_id: OOMPAH-977
    digest: d61b9504e61f8192ec0fce70a3dd27c167c43ea336253b93f1a0afc47f82f701
  - version: 1
    audit_id: audit-c5354a243a91
    project_id: proj-14849f1b
    task_id: OOMPAH-977
    digest: d61b9504e61f8192ec0fce70a3dd27c167c43ea336253b93f1a0afc47f82f701
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1b8d08d9006f
    project_id: proj-14849f1b
    task_id: OOMPAH-977
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d61b9504e61f8192ec0fce70a3dd27c167c43ea336253b93f1a0afc47f82f701
    attempts:
    - version: 1
      attempt_id: attempt-586512c1e66f
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d61b9504e61f8192ec0fce70a3dd27c167c43ea336253b93f1a0afc47f82f701
      created_at: '2026-08-09T23:11:24.010630+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T23:11:24.010630+00:00'
      branch_key: OOMPAH-977
      selected_ref: f8467e42bad3c7db6d47678539ec62fc852e464e
      selected_sha: f8467e42bad3c7db6d47678539ec62fc852e464e
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-09T23:08:32.944952+00:00'
    selected_ref: f8467e42bad3c7db6d47678539ec62fc852e464e
    selected_sha: f8467e42bad3c7db6d47678539ec62fc852e464e
    updated_at: '2026-08-09T23:11:24.010630+00:00'
  - version: 1
    audit_id: audit-c5354a243a91
    project_id: proj-14849f1b
    task_id: OOMPAH-977
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d61b9504e61f8192ec0fce70a3dd27c167c43ea336253b93f1a0afc47f82f701
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-09T23:08:32.944952+00:00'
    selected_ref: f8467e42bad3c7db6d47678539ec62fc852e464e
    selected_sha: f8467e42bad3c7db6d47678539ec62fc852e464e
  attempt_history:
  - version: 1
    attempt_id: attempt-586512c1e66f
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d61b9504e61f8192ec0fce70a3dd27c167c43ea336253b93f1a0afc47f82f701
    created_at: '2026-08-09T23:11:24.010630+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T23:11:24.010630+00:00'
    branch_key: OOMPAH-977
    selected_ref: f8467e42bad3c7db6d47678539ec62fc852e464e
    selected_sha: f8467e42bad3c7db6d47678539ec62fc852e464e
---
## Summary

Discovered during OOMPAH-976 branch hygiene after aggressive pruning: the shared repository .git/config retained core.hooksPath=/home/shedwards/.oompah/worktrees/oompah/OOMPAH-858/.oompah-no-hooks after that worktree was removed. ProjectStore._disable_worktree_hooks invokes git config core.hooksPath without --worktree even though extensions.worktreeConfig is enabled, so every task worktree overwrites one shared hook path; pruning the last writer disables commit hooks for main and every surviving worktree. Implementation scope: configure each managed checkout's core.hooksPath in its worktree config, safely migrate only legacy shared Oompah .oompah-no-hooks values, preserve main/pre-commit hooks and the canonical prepare-commit-msg hook, and keep concurrent worktree creation/removal isolated. Relevant code: oompah/projects.py hook installation/worktree creation and tests/test_projects.py/tests/test_commit_hook.py. Required tests: two linked task worktrees retain distinct valid hook paths; pruning either does not break the other or main; legacy shared stale value migrates safely; unrelated operator-configured shared hook path is not erased; canonical trailer hook remains executable/effective. Acceptance: no surviving checkout references a removed worktree hook directory, focused project/commit-hook suites pass, and local shared configuration is repaired without touching task files.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 23:00
---
Implementation pushed at exact head f8467e42bad3c7db6d47678539ec62fc852e464e on main parent 25154c8. Managed task worktrees now use worktree-local core.hooksPath, narrowly migrate only legacy Oompah sibling paths, and preserve operator/main hooks. Project + commit-hook suites: 193 passed; terminal mutation scan passed. Protected PR #786 is running Python 3.11/3.12/3.13.
---
author: oompah
created: 2026-08-09 23:00
---
Worktree-local hook isolation implemented and protected PR #786 opened
---
author: oompah
created: 2026-08-09 23:08
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 23:11
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 23:11
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
