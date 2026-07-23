---
id: OOMPAH-417
type: task
status: Open
priority: null
title: 'Regression tests: stall-to-recovery path and orphan-reset dispatch integration'
parent: OOMPAH-414
children: []
blocked_by:
- OOMPAH-415
- OOMPAH-416
labels: []
assignee: null
created_at: '2026-07-23T19:34:44.997439Z'
updated_at: '2026-07-23T19:43:42.506387Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Problem

There is no integrated regression test covering the full July 23 stall scenario: scheduler stalls, is detected within the new threshold (from OOMPAH-415), orphan resets are made (from OOMPAH-416), dispatch wakes, and eligible tasks are dispatched. The existing tests in test_dispatch_loop_heartbeat.py cover detection and recovery in isolation, but not the combined stall → orphan-reset → REFRESH_REQUESTED → dispatch path.

### Prerequisites

Depends on OOMPAH-415 (new dispatch_stale_threshold_ms config) and OOMPAH-416 (REFRESH_REQUESTED after orphan resets) being merged first.

### Scope

In tests/test_dispatch_loop_heartbeat.py (or a new file tests/test_stall_recovery_regression.py):

Add the following scenarios, following existing patterns using MagicMock orchestrators:

(a) Stall+recovery within new threshold:
  - Configure dispatch_stale_threshold_ms=2000 and dispatch_stale_grace_ms=500 (small values for fast test)
  - Advance time to simulate a stall past the threshold
  - Call check_and_recover_dispatch_loop() repeatedly; verify recovery is triggered before the old 15-minute threshold would have fired

(b) Orphan-reset + dispatch wake integration:
  - Set up an orchestrator with one orphaned In Progress task (no running agent)
  - Call _reset_orphaned_in_progress() and capture events posted
  - Verify a REFRESH_REQUESTED event was posted
  - Verify the task status was set to Open (via mock tracker)

(c) Exocomp-style clean dispatch after stall recovery:
  - Simulate a scheduler that stalled (no tick for 3 min) with no running agents
  - Trigger recovery (restart)
  - Simulate a fresh tick with two orphaned-then-reset tasks now Open
  - Verify both tasks are dispatched (dispatched_count == 2)

Also: run make test to verify the full test suite passes (all existing tests + new regression tests).

### Acceptance

make test passes cleanly. The three regression scenarios above are all green. The new tests would have caught the July 23 incident if they had existed before.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

