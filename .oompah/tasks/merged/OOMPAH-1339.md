---
id: OOMPAH-1339
type: bug
status: Merged
priority: null
title: WorkflowJobStore reopens SQLite without reopening authority lock fd after orchestrator
  replacement
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-25T17:06:31.999323Z'
updated_at: '2026-08-25T17:53:04.890819Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 6bfbe7cd-9636-4871-b6e9-62d93de0b66a
  request_fingerprint: f24e943b5e6131e0adbc23102abf8f7da3216631cfbddeeecf46021130d96f4d
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-bc4ca808c89c
    project_id: proj-14849f1b
    task_id: OOMPAH-1339
    digest: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
  - version: 1
    audit_id: audit-4d14c45d66a2
    project_id: proj-14849f1b
    task_id: OOMPAH-1339
    digest: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1339","audit-bc4ca808c89c","attempt-97aa86d601a4"]': '2026-08-25T17:44:37.417479+00:00'
    '["proj-14849f1b","OOMPAH-1339","audit-4d14c45d66a2","attempt-6689ccab8ba7"]': '2026-08-25T17:53:00.270272+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1339
    target_state: Done
    evidence_fingerprint: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
    workflow_revision: null
    selected_ref: origin/OOMPAH-1339
    selected_sha: 03bec6e4fa7ab35f7ea6349b51537c4e356766ed
    landing_revision: null
    audit_ids:
    - audit-bc4ca808c89c
    kind: result
    applied: true
    retired_at: '2026-08-25T17:44:37.417496+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1339
    target_state: Merged
    evidence_fingerprint: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
    workflow_revision: null
    selected_ref: origin/OOMPAH-1339
    selected_sha: 03bec6e4fa7ab35f7ea6349b51537c4e356766ed
    landing_revision: null
    audit_ids:
    - audit-4d14c45d66a2
    kind: result
    applied: true
    retired_at: '2026-08-25T17:53:00.270291+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1339
    audit_id: audit-bc4ca808c89c
    attempt_id: attempt-97aa86d601a4
    target_state: Done
    evidence_fingerprint: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
    status: In Validation
    audit_ids:
    - audit-bc4ca808c89c
    kind: result
    applied: true
    created_at: '2026-08-25T17:44:37.417507+00:00'
    applied_at: '2026-08-25T17:44:44.842672+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1339
    audit_id: audit-4d14c45d66a2
    attempt_id: attempt-6689ccab8ba7
    target_state: Merged
    evidence_fingerprint: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
    status: Merged
    audit_ids:
    - audit-4d14c45d66a2
    kind: result
    applied: false
    created_at: '2026-08-25T17:53:00.270303+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-bc4ca808c89c
    project_id: proj-14849f1b
    task_id: OOMPAH-1339
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
    attempts:
    - version: 1
      attempt_id: attempt-97aa86d601a4
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
      created_at: '2026-08-25T17:33:48.189501+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-25T17:33:48.189501+00:00'
      branch_key: OOMPAH-1339
      selected_ref: origin/OOMPAH-1339
      selected_sha: 03bec6e4fa7ab35f7ea6349b51537c4e356766ed
      verdict: pass
      completed_at: '2026-08-25T17:44:37.417275+00:00'
      ended_at: '2026-08-25T17:44:37.417275+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-25T17:27:58.896529+00:00'
    eligible_at: '2026-08-25T17:27:58.896529+00:00'
    selected_ref: origin/OOMPAH-1339
    selected_sha: 03bec6e4fa7ab35f7ea6349b51537c4e356766ed
    updated_at: '2026-08-25T17:44:37.417275+00:00'
  - version: 1
    audit_id: audit-4d14c45d66a2
    project_id: proj-14849f1b
    task_id: OOMPAH-1339
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
    attempts:
    - version: 1
      attempt_id: attempt-6689ccab8ba7
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
      created_at: '2026-08-25T17:45:19.098665+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-25T17:45:19.098665+00:00'
      branch_key: OOMPAH-1339
      selected_ref: origin/OOMPAH-1339
      selected_sha: 03bec6e4fa7ab35f7ea6349b51537c4e356766ed
      verdict: pass
      completed_at: '2026-08-25T17:53:00.270096+00:00'
      ended_at: '2026-08-25T17:53:00.270096+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-25T17:27:58.896529+00:00'
    prerequisite_audit_id: audit-bc4ca808c89c
    selected_ref: origin/OOMPAH-1339
    selected_sha: 03bec6e4fa7ab35f7ea6349b51537c4e356766ed
    updated_at: '2026-08-25T17:53:00.270096+00:00'
    eligible_at: '2026-08-25T17:44:37.417275+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-97aa86d601a4
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
    created_at: '2026-08-25T17:33:48.189501+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-25T17:33:48.189501+00:00'
    branch_key: OOMPAH-1339
    selected_ref: origin/OOMPAH-1339
    selected_sha: 03bec6e4fa7ab35f7ea6349b51537c4e356766ed
  - version: 1
    attempt_id: attempt-6689ccab8ba7
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b002c8352ba6fc7f6bf480630fa72c5d8c01660e66ddbc0d61c04c90a1d8b178
    created_at: '2026-08-25T17:45:19.098665+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-25T17:45:19.098665+00:00'
    branch_key: OOMPAH-1339
    selected_ref: origin/OOMPAH-1339
    selected_sha: 03bec6e4fa7ab35f7ea6349b51537c4e356766ed
oompah.lifecycle_revision: 2
oompah.task_costs:
  total_input_tokens: 282
  total_output_tokens: 8481
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 282
      output_tokens: 8481
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 282
    output_tokens: 8481
    cost_usd: 0.0
    recorded_at: '2026-08-25T17:45:00.800014+00:00'
---
## Summary

### Problem
Task submission can persistently fail with HTTP 400 `file descriptor cannot be a negative integer (-1)`. Reproduced while resubmitting TRICKLE-122 after a service/orchestrator lifecycle transition.

### Root cause
`WorkflowJobStore.close()` closes SQLite and sets `_authority_lock_fd = -1`. `_ensure_conn()` explicitly reopens a closed SQLite connection for stale API threads after orchestrator replacement, but `_authority_mutation_guard()` calls `fcntl.flock(self._authority_lock_fd, ...)` before any connection recovery and never reopens the retired lock descriptor. Any stale reference performing a mutation therefore raises ValueError instead of recovering as intended. The existing `_ensure_conn()` docstring explicitly claims to support API-thread races across orchestrator replacement, so connection and authority-lock recovery must be atomic together.

### Scope
- oompah/workflow_jobs.py: centralize safe authority-lock opening; under the existing store RLock, reopen the lock fd when it is negative before flock; preserve O_CLOEXEC/O_NOFOLLOW and 0600 mode.
- Ensure close remains idempotent and never closes a reused unrelated descriptor.
- Ensure a stale store reference after close can recover both SQLite and authority lock consistently, or fail with a typed WorkflowJobStoreError if recovery is intentionally unsupported.

### Tests
- Close a WorkflowJobStore, then invoke a guarded mutating operation that uses `_ensure_conn`; assert it reopens the SQLite connection and lock descriptor and succeeds without ValueError.
- Concurrent close/recovery is serialized by the store lock.
- Repeated close/recover cycles do not leak descriptors or close unrelated reused descriptors.

### Acceptance Criteria
- No mutation path can call flock with fd -1.
- TRICKLE-122 submission no longer fails with negative file descriptor after an orchestrator replacement/restart.
- Existing workflow job store/restart/resource-cleanup tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-25 17:28
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-25 17:33
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-25 17:34
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-25 17:44
---
Audit PASS — Done

OOMPAH-1339 implementation complete and verified. WorkflowJobStore now safely recovers both SQLite connection and authority lock descriptor after orchestrator replacement. No mutation path calls flock with fd=-1. All 128 workflow_jobs tests + 234 workflow infrastructure tests pass. Repeated close/recovery cycles are safe and don't leak descriptors. Ready for production.

Safe evidence:
- implementation_summary.key_changes[0]: _authority_mutation_guard checks if fd < 0 and reopens before flock
- implementation_summary.key_changes[1]: _open_authority_lock preserves O_CLOEXEC, O_NOFOLLOW, 0o600
- implementation_summary.key_changes[2]: close() detaches fd before closing (idempotent)
- implementation_summary.key_changes[3]: reentrant close during mutations is rejected
- implementation_summary.files_changed[0]: oompah/workflow_jobs.py
- implementation_summary.files_changed[1]: tests/test_workflow_jobs.py
- implementation_summary.test_results.workflow_jobs_tests: 128/128 passed
- implementation_summary.test_results.close_recover_restart_tests: 127/127 passed
- implementation_summary.test_results.workflow_infrastructure_tests: 234/234 passed
- acceptance_criteria.no_flock_negative_fd: PASS - fd recovered before flock in _authority_mutation_guard
- acceptance_criteria.trickle_122_submission: PASS - automatic fd recovery prevents submission failure
- acceptance_criteria.existing_tests_pass: PASS - all 362 related tests pass
- key_tests[0]: test_closed_store_recovers_sqlite_and_authority_lock
- key_tests[1]: test_repeated_close_recovery_cycles_do_not_close_unrelated_fd
- key_tests[2]: test_close_rejected_during_authority_mutation
---
author: oompah
created: 2026-08-25 17:45
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 78, Tool calls: 34
- Tokens: 282 in / 8.5K out [8.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 9s
- Log: OOMPAH-1339__20260825T173422Z.jsonl
---
author: oompah
created: 2026-08-25 17:45
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-25 17:45
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
