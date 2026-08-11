---
id: OOMPAH-1078
type: task
status: In Validation
priority: null
title: Prevent manual In Validation transitions from stranding terminal audits
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T10:13:51.547647Z'
updated_at: '2026-08-11T10:55:07.944249Z'
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
  creation_marker: fb2a09ae-ea46-4667-bd75-8a9f367c2db3
  request_fingerprint: d17b7df2e7e113a319d6343a89d928aaeb0be8479b7cfddbb5a52132b5d87d97
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-18237c837d61
    project_id: proj-14849f1b
    task_id: OOMPAH-1078
    digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
  - version: 1
    audit_id: audit-4dfa2cf5c0b5
    project_id: proj-14849f1b
    task_id: OOMPAH-1078
    digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1078","audit-18237c837d61","attempt-872e685ea279"]': '2026-08-11T10:54:43.968523+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1078
    target_state: Done
    evidence_fingerprint: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
    workflow_revision: null
    selected_ref: origin/OOMPAH-1078
    selected_sha: 9c78b999f9b8eeddda14e2c783ea01a688543325
    landing_revision: null
    audit_ids:
    - audit-18237c837d61
    kind: result
    applied: true
    retired_at: '2026-08-11T10:54:43.968546+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1078
    audit_id: audit-18237c837d61
    attempt_id: attempt-872e685ea279
    target_state: Done
    evidence_fingerprint: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
    status: In Validation
    audit_ids:
    - audit-18237c837d61
    kind: result
    applied: true
    created_at: '2026-08-11T10:54:43.968558+00:00'
    applied_at: '2026-08-11T10:54:51.496604+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-18237c837d61
    project_id: proj-14849f1b
    task_id: OOMPAH-1078
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
    attempts:
    - version: 1
      attempt_id: attempt-872e685ea279
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
      created_at: '2026-08-11T10:51:43.940389+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T10:51:43.940389+00:00'
      branch_key: OOMPAH-1078
      selected_ref: origin/OOMPAH-1078
      selected_sha: 9c78b999f9b8eeddda14e2c783ea01a688543325
      verdict: pass
      completed_at: '2026-08-11T10:54:43.968336+00:00'
      ended_at: '2026-08-11T10:54:43.968336+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-11T10:49:57.906153+00:00'
    selected_ref: origin/OOMPAH-1078
    selected_sha: 9c78b999f9b8eeddda14e2c783ea01a688543325
    updated_at: '2026-08-11T10:54:43.968336+00:00'
  - version: 1
    audit_id: audit-4dfa2cf5c0b5
    project_id: proj-14849f1b
    task_id: OOMPAH-1078
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-11T10:49:57.906153+00:00'
    selected_ref: origin/OOMPAH-1078
    selected_sha: 9c78b999f9b8eeddda14e2c783ea01a688543325
  attempt_history:
  - version: 1
    attempt_id: attempt-872e685ea279
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
    created_at: '2026-08-11T10:51:43.940389+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T10:51:43.940389+00:00'
    branch_key: OOMPAH-1078
    selected_ref: origin/OOMPAH-1078
    selected_sha: 9c78b999f9b8eeddda14e2c783ea01a688543325
oompah.task_costs:
  total_input_tokens: 218
  total_output_tokens: 6766
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 218
      output_tokens: 6766
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 218
    output_tokens: 6766
    cost_usd: 0.0
    recorded_at: '2026-08-11T10:55:03.599740+00:00'
---
## Summary

Live regression observed 2026-08-11 on merged build 4be80277a: an authenticated direct owner ran 'oompah task set-status OOMPAH-1077 In Validation' after its shared implementation had merged. The API accepted the nonterminal status and retired the owner claim, but did not atomically stage terminal-audit metadata or a durable terminal_audit job. Subsequent complete workflow publications reported reason_code=evidence.terminal_audit_missing, required_recovery_count=6/materialized_recovery_count=5, no active_job_id for OOMPAH-1077, restart reconstruction remained incomplete, and otherwise valid auditors could not dispatch. Implementation scope: make direct API/CLI/dashboard In Validation transitions impossible to strand. Either reject In Validation as a coordinator-owned status unless an exact audit request/delivery evidence is atomically staged, or route the request through the canonical terminal-audit coordinator transaction. Preserve idempotency, project-owner authentication, exact branch/head/provenance requirements, existing submit and terminal override flows, and rollback on staging failure. Relevant code: API task status route, TaskTransitionService/terminal audit staging, CLI set-status behavior, workflow runtime materialization. Required tests: direct In Progress->In Validation without audit evidence cannot commit a naked status; an authorized canonical staging path writes status plus audit metadata/job atomically; injected job-store/tracker failures leave the original status/claim recoverable; retries are idempotent; dashboard/CLI error is actionable; restart liveness never observes In Validation with missing audit materialization solely from this route. Acceptance: the reproduced OOMPAH-1077 sequence is rejected or atomically produces a pending audit, required/materialized recovery counts remain equal, focused API/transition/audit/runtime tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 10:26
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-1078`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-11 10:50
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 10:51
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 10:51
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 10:54
---
Audit PASS — Done

Implementation prevents manual In Validation transitions from stranding terminal audits. Direct In Validation transitions are rejected with actionable error message, atomically forcing use of terminal-audit coordinator path. All required tests pass: direct rejection with idempotency verified, canonical staging path works correctly, failure atomicity preserved, restart liveness maintained. Authoritative quality gate already passed for exact head sha.

Safe evidence:
- implementation_strategy: Reject direct In Validation transitions with reason_code transition.audit_staging_required, preserving idempotency while forcing atomic coordinator staging
- key_changes.task_transition_service.py: Direct In Validation rejection at lines 1775-1792
- key_changes.server.py: Actionable error message handling for audit_staging_required
- key_changes.tests: test_task_transition_service.py::test_direct_in_validation_requires_atomic_coordinator_staging, test_state_branch_fetch_error.py::test_direct_validation_rejection_is_actionable_and_atomic
- test_coverage: Direct rejection verified, idempotency tested, canonical path works, failure atomicity confirmed, restart liveness preserved
- quality_gate: Protected workflow make test passed for sha 9c78b999f9b8eeddda14e2c783ea01a688543325
---
author: oompah
created: 2026-08-11 10:55
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 58, Tool calls: 26
- Tokens: 218 in / 6.8K out [7.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 11s
- Log: OOMPAH-1078__20260811T105211Z.jsonl
---
<!-- COMMENTS:END -->
