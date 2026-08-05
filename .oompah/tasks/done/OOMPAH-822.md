---
id: OOMPAH-822
type: task
status: Done
priority: null
title: Stop failed lifecycle reconciliation from retry-spinning and starving validation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T06:43:24.581251Z'
updated_at: '2026-08-05T08:45:06.136101Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: OOMPAH-822
  base_branch: epic-OOMPAH-763
  base_sha: 7bf278b09de0a311c1d1050f6733c5fc9f530975
  head_sha: 6a62d9658ecc5048bd7b26723927b3937d149989
  integrated_sha: 6a62d9658ecc5048bd7b26723927b3937d149989
  submitted_at: '2026-08-05T08:17:16.833275+00:00'
  updated_at: '2026-08-05T08:31:16.338938+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-85f596947ab4: '2026-08-05T08:44:54.479648+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-822
    target_state: Done
    evidence_fingerprint: 603c9883af622273b909103cb19720b0be112267ddfb85d366c625e4cfb2c292
    audit_ids:
    - audit-8764a6c3f4a9
    kind: result
    applied: true
    retired_at: '2026-08-05T08:44:54.479659+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-822
    audit_id: audit-8764a6c3f4a9
    attempt_id: attempt-85f596947ab4
    target_state: Done
    evidence_fingerprint: 603c9883af622273b909103cb19720b0be112267ddfb85d366c625e4cfb2c292
    status: Done
    audit_ids:
    - audit-8764a6c3f4a9
    applied: true
    created_at: '2026-08-05T08:44:54.479675+00:00'
    applied_at: '2026-08-05T08:45:03.656246+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-8764a6c3f4a9
    project_id: proj-14849f1b
    task_id: OOMPAH-822
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 603c9883af622273b909103cb19720b0be112267ddfb85d366c625e4cfb2c292
    attempts:
    - version: 1
      attempt_id: attempt-85f596947ab4
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 603c9883af622273b909103cb19720b0be112267ddfb85d366c625e4cfb2c292
      created_at: '2026-08-05T08:31:45.455755+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T08:31:45.455755+00:00'
      branch_key: OOMPAH-822
      verdict: pass
      completed_at: '2026-08-05T08:44:54.479462+00:00'
      ended_at: '2026-08-05T08:44:54.479462+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-05T08:31:18.921787+00:00'
    updated_at: '2026-08-05T08:44:54.479462+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-85f596947ab4
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 603c9883af622273b909103cb19720b0be112267ddfb85d366c625e4cfb2c292
    created_at: '2026-08-05T08:31:45.455755+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T08:31:45.455755+00:00'
    branch_key: OOMPAH-822
---
## Summary

Live production regression on 2026-08-05: terminal lifecycle reconciliation repeatedly selects the same four failed rows (OOMPAH-452/453/455/456, lifecycle_metadata_not_finalized), each now above 30,000 attempts. reconcile_lifecycle_batch includes failed rows in every first batch and the orchestrator reschedules at 0.01s while any pending work remains, causing PID 3339192 to atomically rewrite+fsync the full ~835 KiB service_state.json roughly 10-13 times/sec (~10.7 MiB/s). The sole OOMPAH-814 exact gate then has all four workers blocked in jbd2_log_wait_commit even with no competing validation suite. Implementation scope: separate fresh pending work from retryable failed rows; give failures durable next-at/backoff and bounded attempt/exhaustion policy; prevent failed rows from monopolizing the cursor; coalesce persistence to one bounded checkpoint per batch; schedule from the earliest due item with a nonzero floor; expose stable degraded/action-required state without a hot loop; and allow operator retry after the underlying metadata issue changes. Preserve per-row isolation, restart safety, exact lifecycle fencing, responsive health/state, and successful pending convergence. Relevant code: oompah/terminal_audit_enforcement.py reconcile_lifecycle_batch/state schema and oompah/orchestrator.py lifecycle scheduler/persistence. Required tests: permanent four-row failure with additional pending rows, retry backoff across restart, no starvation, bounded state writes/wakeups, transient recovery, concurrent schedule coalescing, and a validation subprocess remaining runnable under degraded lifecycle state. Acceptance: unchanged failed rows cannot cause more than the configured bounded retry cadence or continuous state fsync, pending rows drain fairly, and heavyweight validation is not I/O-starved by lifecycle maintenance.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 08:03
---
Reviewed logical lifecycle-reconciliation patch is recorded on the systemic parent branch and pushed at exact clean head 6a62d9658ecc5048bd7b26723927b3937d149989. This is the same reviewed bootstrap logic now deployed on main via OOMPAH-823: bounded retry/backoff and exhaustion, pending-first fairness, coalesced persistence/scheduling, lossless rediscovery, and responsive cached state reads. Verification on this parent-based branch: 217 focused tests passed; terminal mutation scan 8/8 passed; check-secrets and git diff checks passed. Holding submit only until the active OOMPAH-823 terminal audit releases the validation lane.
---
author: oompah
created: 2026-08-05 08:17
---
Record the reviewed lifecycle reconciliation scheduler repair on the systemic parent branch at exact head 6a62d9658: bounded durable retry/backoff and exhaustion, pending-first fairness, coalesced persistence/scheduling, lossless rediscovery, and responsive state API; 217 focused tests and required scans pass.
---
author: oompah
created: 2026-08-05 08:31
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 08:31
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 08:31
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 08:45
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_sha: 6a62d9658ecc5048bd7b26723927b3937d149989
- remote_head_match: origin/OOMPAH-822==HEAD
- merge_base_main: 9ea2b5523f250ac6259531c2e4fae39dff2288bd
- focused_tests_terminal_audit_enforcement: 63/63 pass
- focused_tests_state_api_responsiveness: 20/20 pass
- focused_tests_config: 117/117 pass
- focused_tests_checkpoint_coalescing: 62/62 pass
- focused_tests_terminal_audit_meta: 57/57 pass
- focused_tests_orchestrator_handlers_group: 317/317 pass
- config_batch_size_default: 4
- config_max_attempts_default: 5
- config_retry_backoff_seconds_default: 30
- config_max_backoff_seconds_default: 3600
- config_scheduler_floor_seconds_default: 1.0
- lifecycle_fix_also_on_main_via_OOMPAH_823: d509c0821+2f9984c6a
- diff_stat_lifecycle_change_touches: oompah/config.py, oompah/orchestrator.py, oompah/terminal_audit_enforcement.py, tests
---
<!-- COMMENTS:END -->
