---
id: OOMPAH-640
type: task
status: Open
priority: null
title: Complete combined stall-to-dispatch recovery regression coverage
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T05:59:47.260716Z'
updated_at: '2026-07-31T06:04:53.858932Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ac81c38f3684a776100adff1365492d7e4f68e5c3580a6447826a757979893cb
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 50734c16-7f27-40d7-9a78-0bd67d646f08
  claim_owner: d12922aa-baf6-4258-aa45-02da3deea710
  claimed_at: '2026-07-31T06:04:47.383687+00:00'
  claim_expires_at: '2026-07-31T06:34:47.383687+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 2ece76fd-3703-4c4f-8be6-9887ccebb834
---
## Summary

Follow-up to OOMPAH-417 after parent epic OOMPAH-414 merged. Implementation scope: add the missing integrated regression that exercises a stale dispatch loop recovery, orphaned In Progress tasks reset to Open, the REFRESH_REQUESTED wake, and dispatch of both recovered tasks on the next event-driven tick. Reuse the shipped OOMPAH-415 threshold behavior and OOMPAH-416 orphan-reset wake; do not rewrite those features. Relevant files: tests/test_dispatch_loop_heartbeat.py, tests/test_orphan_reset_dispatch_wake.py, or a focused new regression module, with only production changes if the combined test exposes a real bug. Required tests: prove recovery occurs before the legacy 15-minute threshold; prove one wake is posted after multiple resets; prove two recovered eligible tasks are dispatched without waiting for full sync; cover duplicate wake/tick idempotency. Acceptance: the combined July 23 failure path is deterministic and green, focused tests pass, terminal mutation scan passes, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:04
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
