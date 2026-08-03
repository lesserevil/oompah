---
id: OOMPAH-628
type: bug
status: Done
priority: 1
title: Rearm explicitly resubmitted integrated queue rows
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T22:37:04.318940Z'
updated_at: '2026-08-03T20:05:07.448562Z'
work_branch: epic-OOMPAH-585
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.integration:
  version: 1
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-585--task-OOMPAH-628
  base_branch: epic-OOMPAH-585
  base_sha: 2a8fc4a4b3a101c15e2fea0608480f783f9f3e28
  head_sha: b8c6817b12744e164a2de65b3c49ce8e3ce2b551
  integrated_sha: b8c6817b12744e164a2de65b3c49ce8e3ce2b551
  submitted_at: '2026-07-30T22:41:28.108593+00:00'
  updated_at: '2026-07-30T22:46:48.872338+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-0aef35cc12c3: '2026-07-30T23:02:08.480330+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-8ce7c57923b4
    project_id: proj-14849f1b
    task_id: OOMPAH-628
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c7535256b90ab40432fa0e116cda3512dc6c83a2e7334610672d5c8f46e8b018
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup
      contains this previously audited Done child; durable integration-queue/rollup
      evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.'
    created_at: '2026-08-02T18:29:05.492023+00:00'
    applied: true
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
    reconciled_at: '2026-08-03T20:05:04.944024+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-628
    target_state: Merged
    evidence_fingerprint: c7535256b90ab40432fa0e116cda3512dc6c83a2e7334610672d5c8f46e8b018
    audit_ids:
    - audit-2f03e5509604
    kind: override
    applied: false
    retired_at: '2026-08-02T18:29:13.351873+00:00'
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
  oompah.terminal_audit_result_intents: []
  oompah.lifecycle_reconciliations:
  - project_id: proj-14849f1b
    task_id: OOMPAH-628
    from: Merged
    to: Done
    reason: shared_epic_parent_not_landed
    conflict: 'Cannot transition shared-epic child OOMPAH-628 to Merged: parent epic
      OOMPAH-585 could not be verified. The parent review must land on its configured
      target branch first.'
    done_audit_ids:
    - audit-2f03e5509604
    created_at: '2026-08-03T20:05:04.944024+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2f03e5509604
    project_id: proj-14849f1b
    task_id: OOMPAH-628
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 87eacfec78bca7a0b9e1ded75ba2ff0de471743246c18e3bd452045c916b811d
    attempts:
    - version: 1
      attempt_id: attempt-62700fcd7450
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 87eacfec78bca7a0b9e1ded75ba2ff0de471743246c18e3bd452045c916b811d
      created_at: '2026-07-30T22:50:02.911008+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T22:50:02.911008+00:00'
      branch_key: OOMPAH-628
      failure_classification: infrastructure_error
      ended_at: '2026-07-30T22:51:52.412521+00:00'
      failure_reason: normal
      next_retry_at: '2026-07-30T22:52:02.412491+00:00'
    - version: 1
      attempt_id: attempt-0aef35cc12c3
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 87eacfec78bca7a0b9e1ded75ba2ff0de471743246c18e3bd452045c916b811d
      created_at: '2026-07-30T22:58:47.547933+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-07-30T22:58:47.547933+00:00'
      branch_key: OOMPAH-628
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-07-30T23:02:08.480207+00:00'
      ended_at: '2026-07-30T23:02:08.480207+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T22:46:51.130292+00:00'
    updated_at: '2026-07-30T23:02:08.480207+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-62700fcd7450
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 87eacfec78bca7a0b9e1ded75ba2ff0de471743246c18e3bd452045c916b811d
    created_at: '2026-07-30T22:50:02.911008+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T22:50:02.911008+00:00'
    branch_key: OOMPAH-628
    failure_classification: infrastructure_error
    ended_at: '2026-07-30T22:51:52.412521+00:00'
    failure_reason: normal
    next_retry_at: '2026-07-30T22:52:02.412491+00:00'
  - version: 1
    attempt_id: attempt-0aef35cc12c3
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 87eacfec78bca7a0b9e1ded75ba2ff0de471743246c18e3bd452045c916b811d
    created_at: '2026-07-30T22:58:47.547933+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-07-30T22:58:47.547933+00:00'
    branch_key: OOMPAH-628
    candidate_rotation_count: 1
oompah.task_costs:
  total_input_tokens: 9
  total_output_tokens: 663
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 9
      output_tokens: 663
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 451
    cost_usd: 0.0
    recorded_at: '2026-07-30T22:51:52.228719+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 3
    output_tokens: 212
    cost_usd: 0.0
    recorded_at: '2026-07-30T23:02:34.558813+00:00'
oompah.work_branch: epic-OOMPAH-585
---
## Summary

Implementation scope: distinguish an explicit operator resubmission of a task whose tracker lifecycle was deliberately returned to Ready to Integrate from background synchronization of an already-integrated queue row. Allow the explicit API/CLI submit path to rearm the identical task branch and head only when the canonical task integration record is newly Ready, while preserving idempotency for duplicate submissions in Ready or Integrating and for periodic synchronization. This repairs the observed OOMPAH-627 state where supported Done-to-Ready reflow wrote a new ready integration record but IntegrationQueueStore.enqueue returned the old integrated row forever. Relevant files: oompah/integration_queue.py, server submission wiring, orchestrator synchronization, and focused queue/submission tests. Tests must reproduce same-head integrated explicit reflow, prove background sync remains integrated/idempotent, prove ordinary duplicate active submissions do not reset leases or attempts, and run the focused tests plus the Makefile gate. Acceptance criteria: an explicitly reflowed same-head task cannot remain stranded in Ready to Integrate behind an integrated durable row; no automatic duplicate integration loop is introduced; all focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 22:37
---
Claimed directly to repair the live same-head integration queue deadlock before completing the epic rollout.
---
author: oompah
created: 2026-07-30 22:41
---
Implemented explicit same-head integrated-row rearming behind a fresh-ready evidence fence; background and active-row idempotency remain unchanged.
---
author: oompah
created: 2026-07-30 22:41
---
Implementation complete at b8c6817b12744e164a2de65b3c49ce8e3ce2b551. Verification: 26 focused integration-queue/task-handoff tests passed; expanded queue/handoff/orchestrator suite reported 302 passed; terminal mutation scan passed. Regression covers integrated same-head explicit reflow, background synchronization idempotency, and ready/integrating lease preservation.
---
author: oompah
created: 2026-07-30 22:41
---
Rearm only explicit fresh-ready same-head reflows while preserving automatic and active-row idempotency.
---
author: oompah
created: 2026-07-30 22:46
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 22:47
---
Audit handoff: exact integrated task/epic head is b8c6817b12744e164a2de65b3c49ce8e3ce2b551 and passed the complete Makefile gate. Focused verification: 26 queue/handoff tests passed; expanded queue/handoff/orchestrator run reported 302 passed; terminal mutation scan passed. Review the fresh-ready rearm fence, background idempotency, and active lease preservation, then submit the structured verdict without reimplementation.
---
author: oompah
created: 2026-07-30 22:50
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 22:50
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 22:51
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 3, Tool calls: 0
- Tokens: 6 in / 451 out [457 total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 46s
- Log: OOMPAH-628__20260730T225012Z.jsonl
---
author: oompah
created: 2026-07-30 22:51
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-07-30 22:58
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-07-30 22:58
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 23:02
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: b8c6817b12744e164a2de65b3c49ce8e3ce2b551
- focused_test_count: 30
- focused_test_result: 30 passed in 22.60s
- key_test_explicit_reflow: test_explicit_ready_reflow_rearms_identical_integrated_row PASSED
- key_test_active_idempotency: test_explicit_ready_reflow_does_not_reset_active_row PASSED
- key_test_server_wiring_ready: test_api_submission_marks_queue_enqueue_as_explicit_retry PASSED
- key_test_server_wiring_nonready: test_api_submission_does_not_rearm_without_fresh_ready_record PASSED
- background_sync_idempotency: orchestrator.py integration_queue.enqueue() calls carry no explicit_retry or rearm_integrated
- changed_files: oompah/integration_queue.py (+15 lines), oompah/server.py (+4 lines), tests/test_integration_queue.py (+73 lines), tests/test_task_handoff.py (+30 lines)
---
author: oompah
created: 2026-07-30 23:02
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 61, Tool calls: 39
- Tokens: 3 in / 212 out [215 total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 45s
- Log: OOMPAH-628__20260730T225857Z.jsonl
---
author: oompah
created: 2026-08-02 18:29
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner reconciliation: parent OOMPAH-585 is Merged and its accepted rollup contains this previously audited Done child; durable integration-queue/rollup evidence survives branch pruning. OOMPAH-699 tracks automatic convergence.
---
author: oompah
created: 2026-08-03 20:05
---
Lifecycle reconciliation restored OOMPAH-628 to audited Done: Cannot transition shared-epic child OOMPAH-628 to Merged: parent epic OOMPAH-585 could not be verified. The parent review must land on its configured target branch first.
---
<!-- COMMENTS:END -->
