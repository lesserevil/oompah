---
id: OOMPAH-1091
type: bug
status: In Validation
priority: 1
title: Stop stale accepted-validation recovery after repaired branch advances
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- workflow-liveness
assignee: null
created_at: '2026-08-11T15:35:51.682286Z'
updated_at: '2026-08-11T17:44:03.779646Z'
work_branch: OOMPAH-1091
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/830
review_number: '830'
review_head: 66f40f54566a64b55957ce0a29846289992e2f3f
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: stale-accepted-validation-recovery-after-branch-advance-v1
  request_fingerprint: 06d8f22fc277fa73860a8bc4eb5f0a9186117394a1000d66baab926583e755a8
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1091
  base_branch: main
  base_sha: 3264da6780e35b10f759de8aade7b3509977bbb9
  head_sha: 66f40f54566a64b55957ce0a29846289992e2f3f
  submitted_at: '2026-08-11T16:46:45.273666+00:00'
  updated_at: '2026-08-11T17:00:32.011716+00:00'
oompah.work_branch: OOMPAH-1091
oompah.review_url: https://github.com/lesserevil/oompah/pull/830
oompah.review_number: '830'
oompah.target_branch: main
oompah.review_head: 66f40f54566a64b55957ce0a29846289992e2f3f
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-525e070b511b
    project_id: proj-14849f1b
    task_id: OOMPAH-1091
    digest: 8c4484bec1ff7527ef6a8e2ebb88ddfe197868882da6fa68d5531b65773debdc
  - version: 1
    audit_id: audit-b06217123a35
    project_id: proj-14849f1b
    task_id: OOMPAH-1091
    digest: 8c4484bec1ff7527ef6a8e2ebb88ddfe197868882da6fa68d5531b65773debdc
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1091","audit-525e070b511b","attempt-3f9d5e6bdd17"]': '2026-08-11T17:43:40.168676+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1091
    target_state: Done
    evidence_fingerprint: 8c4484bec1ff7527ef6a8e2ebb88ddfe197868882da6fa68d5531b65773debdc
    workflow_revision: null
    selected_ref: 66f40f54566a64b55957ce0a29846289992e2f3f
    selected_sha: 66f40f54566a64b55957ce0a29846289992e2f3f
    landing_revision: null
    audit_ids:
    - audit-525e070b511b
    kind: result
    applied: true
    retired_at: '2026-08-11T17:43:40.168692+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1091
    audit_id: audit-525e070b511b
    attempt_id: attempt-3f9d5e6bdd17
    target_state: Done
    evidence_fingerprint: 8c4484bec1ff7527ef6a8e2ebb88ddfe197868882da6fa68d5531b65773debdc
    status: In Validation
    audit_ids:
    - audit-525e070b511b
    kind: result
    applied: true
    created_at: '2026-08-11T17:43:40.168702+00:00'
    applied_at: '2026-08-11T17:43:47.752999+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-525e070b511b
    project_id: proj-14849f1b
    task_id: OOMPAH-1091
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8c4484bec1ff7527ef6a8e2ebb88ddfe197868882da6fa68d5531b65773debdc
    attempts:
    - version: 1
      attempt_id: attempt-3f9d5e6bdd17
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8c4484bec1ff7527ef6a8e2ebb88ddfe197868882da6fa68d5531b65773debdc
      created_at: '2026-08-11T17:40:40.858440+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T17:40:40.858440+00:00'
      branch_key: OOMPAH-1091
      selected_ref: 66f40f54566a64b55957ce0a29846289992e2f3f
      selected_sha: 66f40f54566a64b55957ce0a29846289992e2f3f
      verdict: pass
      completed_at: '2026-08-11T17:43:40.168466+00:00'
      ended_at: '2026-08-11T17:43:40.168466+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T17:37:34.030318+00:00'
    eligible_at: '2026-08-11T17:37:34.030318+00:00'
    selected_ref: 66f40f54566a64b55957ce0a29846289992e2f3f
    selected_sha: 66f40f54566a64b55957ce0a29846289992e2f3f
    updated_at: '2026-08-11T17:43:40.168466+00:00'
  - version: 1
    audit_id: audit-b06217123a35
    project_id: proj-14849f1b
    task_id: OOMPAH-1091
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8c4484bec1ff7527ef6a8e2ebb88ddfe197868882da6fa68d5531b65773debdc
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T17:37:34.030318+00:00'
    prerequisite_audit_id: audit-525e070b511b
    selected_ref: 66f40f54566a64b55957ce0a29846289992e2f3f
    selected_sha: 66f40f54566a64b55957ce0a29846289992e2f3f
    updated_at: '2026-08-11T17:43:40.168466+00:00'
    eligible_at: '2026-08-11T17:43:40.168466+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-3f9d5e6bdd17
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8c4484bec1ff7527ef6a8e2ebb88ddfe197868882da6fa68d5531b65773debdc
    created_at: '2026-08-11T17:40:40.858440+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T17:40:40.858440+00:00'
    branch_key: OOMPAH-1091
    selected_ref: 66f40f54566a64b55957ce0a29846289992e2f3f
    selected_sha: 66f40f54566a64b55957ce0a29846289992e2f3f
oompah.task_costs:
  total_input_tokens: 250
  total_output_tokens: 8580
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 250
      output_tokens: 8580
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 250
    output_tokens: 8580
    cost_usd: 0.0
    recorded_at: '2026-08-11T17:43:59.182835+00:00'
---
## Summary

Triggered by: OOMPAH-1085

Live reproduction on OOMPAH-1085: the task is In Progress under a valid direct-owner claim at repaired exact head dcb52a5110f91cab5b6b732f5378ba13fb6a4d27, but retained oompah.integration accepted-submission metadata still names old head 7bd90702b13bfa876f49e5b4e5e27483997945b6. Every workflow reconciliation recreates the old validation_submission generation; repeated jobs reach transition_intent and supersede with transition.generation_mismatch, leaving universal liveness permanently degraded at required_recovery_count=4/materialized_recovery_count=3 even though no task is currently blocked. Repair workflow decision/recovery authority so when an In Progress repaired or direct-owner branch advances beyond a retained accepted submission, the impossible old-head validation obligation is parked/revoked or rebound only through an exact current-head submission; do not silently validate or publish the new head without submission, do not edit tracker metadata out of band, and preserve exact-head/CAS fail-closed behavior. Relevant areas include workflow decision/controller recovery materialization, validation submission authority/revocation, integration metadata reconciliation, and liveness projections. Add deterministic tests for branch advance before and across restart/reconcile, repeated ticks without generation-mismatch job churn, correct direct-owner behavior, exact current-head resubmission convergence, and recovery counts returning complete with no unexplained divergence. Run focused workflow/controller/liveness/submission tests, restart reconstruction tests, terminal mutation scan, and the canonical branch gate. Acceptance: no stale old-head validation job is regenerated after branch advance; no current-head validation is fabricated; exact resubmission converges once; required and materialized recovery counts agree; health is not degraded; and concurrent tracker/main changes remain fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 15:52
---
Implementation is committed and pushed at exact head 423161adc09e447d172409e785f098323e5f45b5. Diagnosis: In Progress crash recovery treated retained accepted-submission metadata as current without revalidating the mutable remote task branch, so OOMPAH-1085 repeatedly rematerialized old-head validation jobs (7bd90702...) whose workflow generation could not match the live direct-owner assignment. Fix: stable remote branch/head revalidation parks unavailable, advanced, or racing accepted evidence; parked recovery suppresses lower-priority handoff/duplicate actions; exact recovered direct-owner validation carries the captured claim ID through TaskTransitionService; only an explicit verified current-head submit can materialize replacement validation. Regression coverage proves repeated reconcile retires the old lane at 0 required/0 materialized, restart does not resurrect it, exact resubmit creates one current 1/1 obligation, claim ABA/unavailable observations fail closed, and the exact claim transition commits once. Checks: 303 focused workflow/adapter/runtime tests passed; 90 owner-claim/submission tests passed; terminal status scan 21/21; diff and secret checks passed. Ready for independent exact-head review; not submitted or merged.
---
author: oompah
created: 2026-08-11 16:21
---
Independent-review follow-up is committed and pushed at replacement head 5e86477733b7f30bf41e333a8d2c483cc12be0a2. The commit-time TOCTOU is closed: ordinary workflow mutations now support a final project-scoped mutation guard; validation submission re-reads the durable originating job, stable live remote task-branch head, and exact current direct-owner claim inside the same project publication lock as the final tracker read/write. A late remote advance, missing/unavailable authority, or owner-claim ABA rejects with transition.stale_precondition and cannot reach Ready to Integrate. Deterministic precommit-barrier regressions cover remote advance and a durably persisted owner-claim replacement after job/fact materialization; restart replay stays rejected and an explicit new exact-head submission converges once. Evidence: 428 runtime/transition/incident tests passed; 7 focused direct-owner validation tests passed; 43 submission-fencing/worker-submission tests passed; terminal mutation scan 21/21; staged and repository secret scans plus commit hooks passed. Branch remains In Progress for independent review; not submitted or merged.
---
author: oompah
created: 2026-08-11 16:46
---
Fresh independent review ACCEPTED replacement exact head 9596e809554d9232b9049621a0858a515c890026. Reviewer verified the prior real ProjectStore RLock watchdog deadlock is closed by limiting guarded off-thread commit authority to implementation.validation_submission, while exact live remote-head and owner-claim ABA checks remain fail-closed at the commit boundary. Independent evidence: 518 candidate tests, 524 clean-current-main merge tests, six deterministic remote/claim/restart/RLock probes, terminal mutation scan 21/21, clean diff. Rebased the exact three-commit series onto current origin/main 3264da678 with git range-diff proving all three commits patch-equivalent, yielding current head 66f40f54566a64b55957ce0a29846289992e2f3f; reran all eight changed race/restart/RLock nodes successfully, pushed with exact force-with-lease. Submitting current-base head.
---
author: oompah
created: 2026-08-11 16:47
---
Stop stale accepted-validation recovery after remote or owner authority advances; revalidate exact authority at commit and avoid watchdog cross-thread project-lock reentry.
---
author: oompah
created: 2026-08-11 16:57
---
Branch quality gate passed for `66f40f54566a64b55957ce0a29846289992e2f3f` using `make test` in 189.6s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 17:12
---
Branch quality gate passed for `66f40f54566a64b55957ce0a29846289992e2f3f` using `make test` in 178.6s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 17:37
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 17:40
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 17:40
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 17:43
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- root_cause: In Progress crash recovery treated retained accepted-submission metadata as current without revalidating mutable remote task branch
- fix_components.remote_branch_revalidation: orchestrator.py:14620-14632 observes live remote head, detects advance
- fix_components.recovery_parking: returns False with accepted_submission_branch_advanced reason code
- fix_components.commit_time_guard: orchestrator.py:5610-5681 _validation_submission_transition_conflict re-reads submission origin, remote head, owner-claim under project write lock
- fix_components.fail_closed: transition.stale_precondition returned on remote or claim race before commit
- test_coverage.branch_advance_parking: test_direct_owner_branch_advance_parks_stale_submission_recovery
- test_coverage.claim_identity_preservation: test_direct_owner_exact_submission_recovery_carries_claim_identity
- test_coverage.toctou_rejection: test_materialized_validation_fails_closed_when_remote_advances_before_commit
- test_coverage.fail_closed_behaviors: test_direct_owner_submission_recovery_fails_closed_on_remote_or_claim_race
- acceptance_criteria.no_stale_old_head_regeneration: parked recovery suppresses validation_submission creation
- acceptance_criteria.no_current_head_fabrication: explicit verified current-head submit required
- acceptance_criteria.exact_resubmit_convergence: captured claim_id in payload prevents duplicate creation
- acceptance_criteria.recovery_count_agreement: single recovery lifecycle demonstrated in tests
- acceptance_criteria.health_not_degraded: recovery state tracking prevents generation-mismatch loops
- acceptance_criteria.fail_closed_concurrent_changes: precommit barrier + project write lock prevents interleaving
- gate_evidence.command: make test
- gate_evidence.duration_seconds: 178.58
- gate_evidence.result: passed
- gate_evidence.status: passed
- gate_evidence.authority_current: true
---
author: oompah
created: 2026-08-11 17:44
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 66, Tool calls: 30
- Tokens: 250 in / 8.6K out [8.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 11s
- Log: OOMPAH-1091__20260811T174105Z.jsonl
---
<!-- COMMENTS:END -->
