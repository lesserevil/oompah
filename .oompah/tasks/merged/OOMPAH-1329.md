---
id: OOMPAH-1329
type: task
status: Merged
priority: null
title: Stop over-budget workflow reconciliation from hot-looping worker admission
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T01:36:28.768799Z'
updated_at: '2026-08-24T02:35:55.684994Z'
work_branch: OOMPAH-1329
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/907
review_number: '907'
review_head: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 371719b5-9bbc-4ef2-9eb3-463362b66297
  request_fingerprint: 42c3c0fde84cd2ad321f76f112089c3ffe9d915f0fc8cafd65d70f412596c940
oompah.lifecycle_revision: 5
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1329
  base_branch: main
  base_sha: 1d2953c14bc925aaef79a40cd33fd3ea280ff6a4
  head_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
  submitted_at: '2026-08-24T01:50:18.216653+00:00'
  updated_at: '2026-08-24T01:50:18.216653+00:00'
oompah.work_branch: OOMPAH-1329
oompah.review_url: https://github.com/lesserevil/oompah/pull/907
oompah.review_number: '907'
oompah.target_branch: main
oompah.review_head: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-d2d1717d9afd
    project_id: proj-14849f1b
    task_id: OOMPAH-1329
    digest: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
  - version: 1
    audit_id: audit-925a61fc1c8f
    project_id: proj-14849f1b
    task_id: OOMPAH-1329
    digest: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1329","audit-d2d1717d9afd","attempt-050fc068b811"]': '2026-08-24T02:27:28.619835+00:00'
    '["proj-14849f1b","OOMPAH-1329","audit-925a61fc1c8f","attempt-6794175ba7a8"]': '2026-08-24T02:35:45.446342+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1329
    target_state: Done
    evidence_fingerprint: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
    workflow_revision: null
    selected_ref: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    selected_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    landing_revision: null
    audit_ids:
    - audit-d2d1717d9afd
    kind: result
    applied: true
    retired_at: '2026-08-24T02:27:28.619852+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1329
    target_state: Merged
    evidence_fingerprint: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
    workflow_revision: null
    selected_ref: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    selected_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    landing_revision: null
    audit_ids:
    - audit-925a61fc1c8f
    kind: result
    applied: true
    retired_at: '2026-08-24T02:35:45.446361+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1329
    audit_id: audit-d2d1717d9afd
    attempt_id: attempt-050fc068b811
    target_state: Done
    evidence_fingerprint: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
    status: In Validation
    audit_ids:
    - audit-d2d1717d9afd
    kind: result
    applied: true
    created_at: '2026-08-24T02:27:28.619863+00:00'
    applied_at: '2026-08-24T02:27:35.595865+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-1329
    audit_id: audit-925a61fc1c8f
    attempt_id: attempt-6794175ba7a8
    target_state: Merged
    evidence_fingerprint: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
    status: Merged
    audit_ids:
    - audit-925a61fc1c8f
    kind: result
    applied: true
    created_at: '2026-08-24T02:35:45.446373+00:00'
    applied_at: '2026-08-24T02:35:53.927291+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d2d1717d9afd
    project_id: proj-14849f1b
    task_id: OOMPAH-1329
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
    attempts:
    - version: 1
      attempt_id: attempt-050fc068b811
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
      created_at: '2026-08-24T02:15:52.518930+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T02:15:52.518930+00:00'
      branch_key: OOMPAH-1329
      selected_ref: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
      selected_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
      verdict: pass
      completed_at: '2026-08-24T02:27:28.619638+00:00'
      ended_at: '2026-08-24T02:27:28.619638+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-24T01:59:28.396034+00:00'
    eligible_at: '2026-08-24T01:59:28.396034+00:00'
    selected_ref: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    selected_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    updated_at: '2026-08-24T02:27:28.619638+00:00'
  - version: 1
    audit_id: audit-925a61fc1c8f
    project_id: proj-14849f1b
    task_id: OOMPAH-1329
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
    attempts:
    - version: 1
      attempt_id: attempt-6794175ba7a8
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
      created_at: '2026-08-24T02:28:02.354610+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-24T02:28:02.354610+00:00'
      branch_key: OOMPAH-1329
      selected_ref: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
      selected_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
      verdict: pass
      completed_at: '2026-08-24T02:35:45.446168+00:00'
      ended_at: '2026-08-24T02:35:45.446168+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-24T01:59:28.396034+00:00'
    prerequisite_audit_id: audit-d2d1717d9afd
    selected_ref: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    selected_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    updated_at: '2026-08-24T02:35:45.446168+00:00'
    eligible_at: '2026-08-24T02:27:28.619638+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-050fc068b811
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
    created_at: '2026-08-24T02:15:52.518930+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T02:15:52.518930+00:00'
    branch_key: OOMPAH-1329
    selected_ref: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    selected_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
  - version: 1
    attempt_id: attempt-6794175ba7a8
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 93d3202e8d44cf80ca57b31cf884a20fd2c8ae2a3a2510a3de337965df5632de
    created_at: '2026-08-24T02:28:02.354610+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-24T02:28:02.354610+00:00'
    branch_key: OOMPAH-1329
    selected_ref: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
    selected_sha: bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
oompah.task_costs:
  total_input_tokens: 658
  total_output_tokens: 15417
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 658
      output_tokens: 15417
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 658
    output_tokens: 15417
    cost_usd: 0.0
    recorded_at: '2026-08-24T02:27:48.744329+00:00'
---
## Summary

The durable workflow runtime can spend longer than the restart correction budget, lose tracker authority at the final publication barrier, return requires_reconcile=true, and immediately enqueue another full reconciliation. Each continuation receives a fresh budget, restart reconstruction remains pending, and normal workflow worker admission stays closed indefinitely. Observed live with 54 Ready to Integrate tasks and zero ordinary workers; reconciliation took ~199s (integration ~144s) against a 120s budget and returned publication_authority_changed. Implement a fail-closed retry disposition: consistently mark generic and scoped publication supersession that completes after the deadline as restart_deadline_exceeded, and do not immediately self-enqueue another reconciliation for that exhausted result. A later periodic or authority-change wake may retry. Add runtime and orchestrator regression tests proving the worker remains closed but no hot continuation loop is generated. Acceptance: no stale jobs are admitted; over-budget supersession is observable; immediate retries stop; a later stable reconciliation can publish and reopen admission.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 01:50
---
Live diagnosis confirmed repeated over-budget publication supersession hot-loops full reconciliation while worker admission remains closed. Implementing explicit exhaustion signaling and suppressing immediate self-requeue.
---
author: oompah
created: 2026-08-24 01:50
---
Over-budget superseded reconciliations now expose restart_deadline_exceeded and do not immediately enqueue another full scan. Focused runtime/orchestrator regression tests pass.
---
author: oompah
created: 2026-08-24 01:53
---
Branch quality gate passed for `bb2cbaf913fb5faefa18ffa59acefaa76d2dfada` using `make test` in 179.5s. Review creation may proceed.
---
author: oompah
created: 2026-08-24 01:59
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-24 02:15
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 02:16
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 02:27
---
Audit PASS — Done

Over-budget publication supersession now explicitly marks restart_deadline_exceeded and suppresses immediate self-requeue. Orchestrator's _request_runtime_report_continuation prevents continuation when deadline exceeded. Worker remains closed but no hot-loop is generated; later periodic or authority-change wake can retry. Regression tests verify behavior. Acceptance criteria met.

Safe evidence:
- test_results.test_over_budget_publication_supersession_is_marked_exhausted: PASSED
- test_results.test_exhausted_superseded_publication_does_not_hot_loop: PASSED
- test_results.full_gate_make_test: PASSED (179.5s)
- implementation_changes.workflow_runtime_py_deadline_exceeded_signals: Lines 2898, 2903, 2924 set restart_deadline_exceeded flag when reconciliation exceeds budget
- implementation_changes.orchestrator_py_suppress_continuation: Method _request_runtime_report_continuation (lines 12611-12624) returns False when restart_deadline_exceeded is True, blocking immediate self-requeue
- implementation_changes.orchestrator_callers: Lines 17353 (_run_restart_reconstruction_tick), 17424 (_run_durable_workflow_tick) call suppression logic
- acceptance_verification[0]: Worker admission stays closed until next periodic or authority-change wake
- acceptance_verification[1]: restart_deadline_exceeded flag observable in all superseded reports
- acceptance_verification[2]: No continuation requested when deadline exceeded
- acceptance_verification[3]: Later reconciliation can publish and reopen admission
---
author: oompah
created: 2026-08-24 02:27
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 169, Tool calls: 81
- Tokens: 658 in / 15.4K out [16.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 53s
- Log: OOMPAH-1329__20260824T021607Z.jsonl
---
author: oompah
created: 2026-08-24 02:28
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-24 02:28
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-24 02:35
---
Audit PASS — Merged

Over-budget workflow reconciliation no longer hot-loops. Implementation correctly marks exhausted deadline with restart_deadline_exceeded flag and suppresses immediate self-requeue. Acceptance criteria met: worker remains closed, over-budget supersession is observable, no hot-loop generated, periodic/authority-change wake can retry later.

Safe evidence:
- implementation_verified.workflow_runtime_py: Lines 2895-2898, 2901-2903, 2924 set restart_deadline_exceeded when over budget
- implementation_verified.orchestrator_py_suppression: Lines 12616-12620 return False in _request_runtime_report_continuation when deadline exceeded, suppressing continuation
- implementation_verified.orchestrator_callers: Lines 17353, 17424 call suppression logic in tick handlers
- focused_regression_tests_run.test_over_budget_publication_supersession_is_marked_exhausted: PASSED
- focused_regression_tests_run.test_exhausted_superseded_publication_does_not_hot_loop: PASSED - continuation_requested=False, admission not awaited
- acceptance_criteria_verification.no_stale_jobs_admitted: Worker admission skipped when deadline exceeded; continue_admission_async not called
- acceptance_criteria_verification.over_budget_supersession_observable: restart_deadline_exceeded flag present in all superseded reports
- acceptance_criteria_verification.immediate_retries_stop: No continuation requested when flag True, blocking hot-loop self-requeue
- acceptance_criteria_verification.later_stable_reconciliation_can_publish: Flag only suppresses immediate continuation; periodic/authority-change wake can retry
- full_gate_status: make test PASSED (179.5s) - exact head bb2cbaf913fb5faefa18ffa59acefaa76d2dfada
- code_inspection: Changes minimal, focused, and correct: deadline tracking + flag setting + suppression check
---
<!-- COMMENTS:END -->
