---
id: OOMPAH-822
type: task
status: Ready to Integrate
priority: null
title: Stop failed lifecycle reconciliation from retry-spinning and starving validation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T06:43:24.581251Z'
updated_at: '2026-08-05T08:17:23.689548Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-822
  head_sha: 6a62d9658ecc5048bd7b26723927b3937d149989
  submitted_at: '2026-08-05T08:17:16.833275+00:00'
  updated_at: '2026-08-05T08:17:16.833275+00:00'
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
<!-- COMMENTS:END -->
