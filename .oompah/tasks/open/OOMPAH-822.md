---
id: OOMPAH-822
type: task
status: Open
priority: null
title: Stop failed lifecycle reconciliation from retry-spinning and starving validation
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-05T06:43:24.581251Z'
updated_at: '2026-08-05T06:44:53.914939Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live production regression on 2026-08-05: terminal lifecycle reconciliation repeatedly selects the same four failed rows (OOMPAH-452/453/455/456, lifecycle_metadata_not_finalized), each now above 30,000 attempts. reconcile_lifecycle_batch includes failed rows in every first batch and the orchestrator reschedules at 0.01s while any pending work remains, causing PID 3339192 to atomically rewrite+fsync the full ~835 KiB service_state.json roughly 10-13 times/sec (~10.7 MiB/s). The sole OOMPAH-814 exact gate then has all four workers blocked in jbd2_log_wait_commit even with no competing validation suite. Implementation scope: separate fresh pending work from retryable failed rows; give failures durable next-at/backoff and bounded attempt/exhaustion policy; prevent failed rows from monopolizing the cursor; coalesce persistence to one bounded checkpoint per batch; schedule from the earliest due item with a nonzero floor; expose stable degraded/action-required state without a hot loop; and allow operator retry after the underlying metadata issue changes. Preserve per-row isolation, restart safety, exact lifecycle fencing, responsive health/state, and successful pending convergence. Relevant code: oompah/terminal_audit_enforcement.py reconcile_lifecycle_batch/state schema and oompah/orchestrator.py lifecycle scheduler/persistence. Required tests: permanent four-row failure with additional pending rows, retry backoff across restart, no starvation, bounded state writes/wakeups, transient recovery, concurrent schedule coalescing, and a validation subprocess remaining runnable under degraded lifecycle state. Acceptance: unchanged failed rows cannot cause more than the configured bounded retry cadence or continuous state fsync, pending rows drain fairly, and heavyweight validation is not I/O-starved by lifecycle maintenance.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

