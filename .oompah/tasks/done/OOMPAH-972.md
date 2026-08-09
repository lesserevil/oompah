---
id: OOMPAH-972
type: task
status: Done
priority: null
title: Repair stale editable installs after worktree retirement
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T20:03:49.482603Z'
updated_at: '2026-08-09T20:45:03.396769Z'
work_branch: OOMPAH-972
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/780
review_number: '780'
review_head: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-972
  head_sha: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
  submitted_at: '2026-08-09T20:25:05.536964+00:00'
  updated_at: '2026-08-09T20:25:05.536964+00:00'
oompah.work_branch: OOMPAH-972
oompah.review_url: https://github.com/lesserevil/oompah/pull/780
oompah.review_number: '780'
oompah.target_branch: main
oompah.review_head: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-086401438eaf
    project_id: proj-14849f1b
    task_id: OOMPAH-972
    digest: 7b7bc1bca3f3a6b5c7665b44fa302e34ebec9b426087ff6170d80c119fc8a269
  - version: 1
    audit_id: audit-421c9eb62469
    project_id: proj-14849f1b
    task_id: OOMPAH-972
    digest: 7b7bc1bca3f3a6b5c7665b44fa302e34ebec9b426087ff6170d80c119fc8a269
  oompah.terminal_override_records:
  - version: 1
    override_id: override-a12bee1da9a1
    project_id: proj-14849f1b
    task_id: OOMPAH-972
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7b7bc1bca3f3a6b5c7665b44fa302e34ebec9b426087ff6170d80c119fc8a269
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-09T20:44:59.171086+00:00'
    selected_ref: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
    selected_sha: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-086401438eaf
    project_id: proj-14849f1b
    task_id: OOMPAH-972
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7b7bc1bca3f3a6b5c7665b44fa302e34ebec9b426087ff6170d80c119fc8a269
    attempts:
    - version: 1
      attempt_id: attempt-6657e818628d
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 7b7bc1bca3f3a6b5c7665b44fa302e34ebec9b426087ff6170d80c119fc8a269
      created_at: '2026-08-09T20:44:47.036853+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T20:44:47.036853+00:00'
      branch_key: OOMPAH-972
      selected_ref: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
      selected_sha: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T20:43:37.512483+00:00'
    selected_ref: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
    selected_sha: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
    updated_at: '2026-08-09T20:44:47.036853+00:00'
  - version: 1
    audit_id: audit-421c9eb62469
    project_id: proj-14849f1b
    task_id: OOMPAH-972
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7b7bc1bca3f3a6b5c7665b44fa302e34ebec9b426087ff6170d80c119fc8a269
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T20:43:37.512483+00:00'
    selected_ref: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
    selected_sha: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
  attempt_history:
  - version: 1
    attempt_id: attempt-6657e818628d
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7b7bc1bca3f3a6b5c7665b44fa302e34ebec9b426087ff6170d80c119fc8a269
    created_at: '2026-08-09T20:44:47.036853+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T20:44:47.036853+00:00'
    branch_key: OOMPAH-972
    selected_ref: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
    selected_sha: 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e
---
## Summary

Aggressive cleanup of merged OOMPAH worktrees exposed a deterministic local-environment bug: the main checkout .venv retained an editable-install .pth pointing at the retired /home/shedwards/src/oompah-967 worktree, while .venv/.uv-setup remained newer than pyproject.toml. Consequently make setup was a no-op and .venv/bin/oompah failed with ModuleNotFoundError until the setup stamp was manually invalidated. Implementation scope: make the setup target validate that the installed oompah package resolves to the current checkout before accepting the idempotency stamp, and reinstall when the editable target is absent or belongs to another worktree; preserve trusted task-private venv checks and normal fast idempotent setup. Relevant files: Makefile/setup helpers and focused setup/install tests. Required tests: reproduce a stale editable target with a fresh setup stamp, prove make setup repairs it to the invoking checkout, prove an already-correct install remains idempotent, and prove task-private interpreter/symlink fail-closed checks remain intact. Acceptance: merged-worktree pruning cannot leave the main oompah CLI unusable, focused tests and protected Python 3.11/3.12/3.13 CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 20:04
---
Accepted for direct-owner repair during the aggressive branch/worktree pruning completion pass; reproduced locally and restored the current CLI only by invalidating the stale setup stamp.
---
author: oompah
created: 2026-08-09 20:24
---
Implementation complete at exact rebased head 9f5bc28fb7daec2d1c0fa35ec46a535c6881272e on main a7c418ee4. Setup now validates the private venv and isolated editable source even with a fresh stamp, refreshes stale worktree targets, preserves the correct-install fast path, and fails before stamp mutation when uv partially updates metadata then exits nonzero. Evidence: 46 focused setup/lifecycle tests, real first-run and repeated idempotent make setup/test-setup, secret scan, diff check, and independent review. Review found and the final commit closed the partial-installer fail-open; narrow re-review passed 3 nodes and full setup module passed 18 with no remaining blocker.
---
author: oompah
created: 2026-08-09 20:25
---
Made setup idempotency safe across retired worktrees, including fail-closed partial-installer behavior; exact rebased head is independently reviewed and all focused setup/lifecycle checks pass.
---
author: oompah
created: 2026-08-09 20:28
---
Branch quality gate passed for `9f5bc28fb7daec2d1c0fa35ec46a535c6881272e` using `make test` in 158.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-09 20:43
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 20:44
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 20:44
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
