---
id: OOMPAH-977
type: task
status: Merged
priority: null
title: Keep managed worktree hook paths worktree-local
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T22:45:47.293153Z'
updated_at: '2026-08-09T23:19:28.805416Z'
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
  oompah.terminal_override_records:
  - version: 1
    override_id: override-ff4569e932c7
    project_id: proj-14849f1b
    task_id: OOMPAH-977
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d61b9504e61f8192ec0fce70a3dd27c167c43ea336253b93f1a0afc47f82f701
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-09T23:18:36.460312+00:00'
    selected_ref: f8467e42bad3c7db6d47678539ec62fc852e464e
    selected_sha: f8467e42bad3c7db6d47678539ec62fc852e464e
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-977
    target_state: Merged
    evidence_fingerprint: d61b9504e61f8192ec0fce70a3dd27c167c43ea336253b93f1a0afc47f82f701
    audit_ids:
    - audit-1b8d08d9006f
    - audit-c5354a243a91
    kind: override
    applied: true
    retired_at: '2026-08-09T23:18:50.763317+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1b8d08d9006f
    project_id: proj-14849f1b
    task_id: OOMPAH-977
    target_state: Done
    request_state: cancelled
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
    updated_at: '2026-08-09T23:18:50.763275+00:00'
  - version: 1
    audit_id: audit-c5354a243a91
    project_id: proj-14849f1b
    task_id: OOMPAH-977
    target_state: Merged
    request_state: cancelled
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
    updated_at: '2026-08-09T23:18:50.763302+00:00'
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
oompah.task_costs:
  total_input_tokens: 106
  total_output_tokens: 18
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 106
      output_tokens: 18
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 106
    output_tokens: 18
    cost_usd: 0.0
    recorded_at: '2026-08-09T23:19:21.571068+00:00'
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
author: oompah
created: 2026-08-09 23:18
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: [REDACTED]
---
author: oompah
created: 2026-08-09 23:19
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 5
- Tokens: 106 in / 18 out [124 total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 54s
- Log: OOMPAH-977__20260809T231138Z.jsonl
---
<!-- COMMENTS:END -->
