---
id: OOMPAH-1331
type: task
status: In Validation
priority: null
title: Restart reconstruction never finalizes (1 unexplained divergence) leaving stale
  action_required=19 and permanent restart_overdue
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T16:28:31.897753Z'
updated_at: '2026-08-24T17:41:21.264214Z'
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
  creation_marker: eaae4288-c737-4655-a501-a014d7a120f1
  request_fingerprint: 0424978c962567958aad57a379d453e5110704b8c4b1b80170bf0f08fca47f38
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-34bc00c97981
    project_id: proj-14849f1b
    task_id: OOMPAH-1331
    digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
  - version: 1
    audit_id: audit-ad3efba187b4
    project_id: proj-14849f1b
    task_id: OOMPAH-1331
    digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1331","audit-34bc00c97981","attempt-fccf5a75d857"]': '2026-08-24T17:16:59.921038+00:00'
    '["proj-14849f1b","OOMPAH-1331","audit-ad3efba187b4","attempt-1d2393768dc7"]': '2026-08-24T17:41:19.461234+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1331
    target_state: Done
    evidence_fingerprint: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
    workflow_revision: null
    selected_ref: origin/OOMPAH-1331
    selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
    landing_revision: null
    audit_ids:
    - audit-34bc00c97981
    kind: result
    applied: true
    retired_at: '2026-08-24T17:16:59.921054+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1331
    audit_id: audit-34bc00c97981
    attempt_id: attempt-fccf5a75d857
    target_state: Done
    evidence_fingerprint: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
    status: In Validation
    audit_ids:
    - audit-34bc00c97981
    kind: result
    applied: true
    created_at: '2026-08-24T17:16:59.921066+00:00'
    applied_at: '2026-08-24T17:17:09.019721+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-34bc00c97981
    project_id: proj-14849f1b
    task_id: OOMPAH-1331
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
    attempts:
    - version: 1
      attempt_id: attempt-fccf5a75d857
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
      created_at: '2026-08-24T17:05:40.482980+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T17:05:40.482980+00:00'
      branch_key: OOMPAH-1331
      selected_ref: origin/OOMPAH-1331
      selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
      verdict: pass
      completed_at: '2026-08-24T17:16:59.920832+00:00'
      ended_at: '2026-08-24T17:16:59.920832+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T16:59:53.820238+00:00'
    eligible_at: '2026-08-24T16:59:53.820238+00:00'
    selected_ref: origin/OOMPAH-1331
    selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
    updated_at: '2026-08-24T17:16:59.920832+00:00'
  - version: 1
    audit_id: audit-ad3efba187b4
    project_id: proj-14849f1b
    task_id: OOMPAH-1331
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
    attempts:
    - version: 1
      attempt_id: attempt-e39bb60fd89a
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
      created_at: '2026-08-24T17:18:24.641085+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T17:18:24.641085+00:00'
      branch_key: OOMPAH-1331
      selected_ref: origin/OOMPAH-1331
      selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
      failure_classification: policy_incompatibility
      ended_at: '2026-08-24T17:28:26.208230+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy denied a path outside the repository worktree'
      next_retry_at: '2026-08-24T17:28:36.208192+00:00'
    - version: 1
      attempt_id: attempt-1d2393768dc7
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
      created_at: '2026-08-24T17:30:28.597834+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-24T17:30:28.597834+00:00'
      branch_key: OOMPAH-1331
      selected_ref: origin/OOMPAH-1331
      selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
      candidate_rotation_count: 1
      verdict: fail
      failure_classification: infrastructure_error
      ended_at: '2026-08-24T17:41:19.461134+00:00'
      failure_reason: retry ceiling reached; verdict left pending
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T16:59:53.820238+00:00'
    prerequisite_audit_id: audit-34bc00c97981
    selected_ref: origin/OOMPAH-1331
    selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
    updated_at: '2026-08-24T17:41:19.461134+00:00'
    eligible_at: '2026-08-24T17:16:59.920832+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-fccf5a75d857
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
    created_at: '2026-08-24T17:05:40.482980+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T17:05:40.482980+00:00'
    branch_key: OOMPAH-1331
    selected_ref: origin/OOMPAH-1331
    selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
  - version: 1
    attempt_id: attempt-e39bb60fd89a
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
    created_at: '2026-08-24T17:18:24.641085+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T17:18:24.641085+00:00'
    branch_key: OOMPAH-1331
    selected_ref: origin/OOMPAH-1331
    selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
    failure_classification: policy_incompatibility
    ended_at: '2026-08-24T17:28:26.208230+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy denied a path outside the repository worktree'
    next_retry_at: '2026-08-24T17:28:36.208192+00:00'
  - version: 1
    attempt_id: attempt-1d2393768dc7
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
    created_at: '2026-08-24T17:30:28.597834+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-24T17:30:28.597834+00:00'
    branch_key: OOMPAH-1331
    selected_ref: origin/OOMPAH-1331
    selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
    candidate_rotation_count: 1
oompah.lifecycle_revision: 1
oompah.task_costs:
  total_input_tokens: 1120
  total_output_tokens: 13849
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1120
      output_tokens: 13849
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 338
    output_tokens: 13665
    cost_usd: 0.0
    recorded_at: '2026-08-24T17:17:42.770795+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 782
    output_tokens: 184
    cost_usd: 0.0
    recorded_at: '2026-08-24T17:28:36.381877+00:00'
---
## Summary

### Problem
workflow_liveness restart reconstruction never marks complete, so the dashboard permanently shows 'N workflow task(s) require a named human action' (source workflow_liveness:action_required) with a frozen count (observed action_required=19). Worker admission stays fenced (worker.skipped: 'workflow publication requires reconciliation before durable admission').

### Live evidence (build 1e08d58a3, main)
- workflow_liveness.restart: reconstruction_pending=true, started_at=2026-08-24T15:41:44Z (does NOT reset across a graceful make restart), lateness_seconds keeps growing (>2000s), convergence_count=132.
- workflow_liveness.reconciliation: complete=false, required_recovery_count=83, materialized_recovery_count=83 (all required recoveries materialized).
- missing_decision_count=0, current_divergence_count=1, unexplained_divergence_count=1, evaluated_count=0, total_nonterminal_count=320.
- workflow_runtime.last_reconcile alternates between requires_reconcile=null and (earlier) requires_reconcile=true reason=publication_authority_changed; worker=skipped.
- The frozen action_required=19 persists across a full service restart and with zero running agents, i.e. it is a stale pre-scan projection that never refreshes because scan_complete stays false.

### Impact
- Non-terminal work cannot be admitted (integration/implementation stay idle) while reconstruction is pending.
- Operators see a persistent, non-actionable 'named human action' alert that does not correspond to 19 real tasks (the per-task records are unpopulated: id/action/reason all null).

### Suspected root cause
Restart reconstruction finalization requires zero unexplained divergences, but 1 unexplained divergence remains even though required_recovery_count == materialized_recovery_count (83) and missing_decision_count == 0. Reconstruction therefore never sets reconciliation.complete=true / scan_complete=true, and the restart record is persisted (not reset) so a restart does not clear it. This is distinct from OOMPAH-1329 (over-budget scoped/deadline supersession) and from the auditor transport crash (OOMPAH-1330).

### Investigation scope
- Find where restart reconstruction decides completeness (workflow_liveness / workflow_runtime restart_reconstruction path) and why a single unexplained divergence blocks finalization after all required recoveries are materialized.
- Identify the specific diverging record (current_divergence_count=1) and classify it; ensure an explained/reconciled divergence cannot remain 'unexplained' forever.
- Ensure restart reconstruction state resets or re-evaluates cleanly on service restart rather than persisting a stuck started_at/deadline.
- Ensure the dashboard action_required projection refreshes (or is suppressed) when scan_complete=false rather than surfacing a stale count.

### Tests
- Reconstruction with all required recoveries materialized and 1 residual explained-but-flagged divergence must still converge to complete=true.
- Restart reconstruction record resets/re-evaluates across runtime restart.
- action_required projection is not surfaced as a stale frozen count while scan_complete=false.

### Acceptance Criteria
- After recoveries are materialized and no genuine human action is pending, restart reconstruction converges (scan_complete=true, reconstruction_pending=false), worker admission reopens, and the 'require a named human action' alert clears.
- A single unexplained divergence cannot indefinitely block finalization.
- A graceful restart re-evaluates reconstruction rather than inheriting a permanently-late record.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 17:00
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-24 17:05
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 17:05
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 17:17
---
Audit PASS — Done

Code review confirms the fix correctly addresses OOMPAH-1331. The implementation introduces source_scan_deferred to distinguish intentional publication deferrals (excluded already-covered tasks) from real source scan failures. When deferred and all reconciliation conditions are met, restart reconstruction now finalizes instead of remaining pending with a phantom unexplained divergence.

Safe evidence:
- fix_overview: Introduced source_scan_deferred flag to allow scan completeness despite source_scan_complete=False when the scan only excluded already-covered terminal-audit disposition changes.
- files_modified[0]: oompah/workflow_controller.py: Added source_scan_deferred field to ControllerObservation
- files_modified[1]: oompah/workflow_liveness_metrics.py: Added source_scan_deferred parameter and source_scan_effectively_complete logic
- files_modified[2]: oompah/workflow_runtime.py: Sets source_scan_deferred=True when publication excludes covered tasks
- files_modified[3]: tests/test_workflow_liveness_metrics.py: Added two regression tests
- acceptance_criteria_addressed.convergence_on_full_materialization: PASS - test_publication_deferred_scan_finalizes_when_fully_reconciled verifies scan_complete=True, restart_reconstruction_pending=False when source_scan_deferred=True with full reconciliation
- acceptance_criteria_addressed.no_divergence_blocks_finalization: PASS - source_scan_deferred eliminates phantom divergence by treating deferred scans as effectively complete
- acceptance_criteria_addressed.graceful_restart_reevaluates: PASS - source_scan_deferred is computed fresh each observation, not persisted
- test_coverage: New tests verify both deferred-finalizes (test_publication_deferred_scan_finalizes_when_fully_reconciled) and fail-closed non-deferred (test_non_deferred_incomplete_scan_still_fails_closed)
- backward_compatibility: PASS - source_scan_deferred defaults to False, preserving existing behavior
- code_quality: PASS - Docstring added explaining source_scan_deferred; logic correctly gates finalization on multiple conditions (no errors, effective reconciliation, deferred flag); changes are isolated and minimal
---
author: oompah
created: 2026-08-24 17:17
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 99, Tool calls: 43
- Tokens: 338 in / 13.7K out [14.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 57s
- Log: OOMPAH-1331__20260824T170606Z.jsonl
---
author: oompah
created: 2026-08-24 17:18
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 17:18
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 17:28
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-24 17:28
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 44
- Tokens: 782 in / 184 out [966 total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 54s
- Log: OOMPAH-1331__20260824T171908Z.jsonl
---
author: oompah
created: 2026-08-24 17:30
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-24 17:30
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
