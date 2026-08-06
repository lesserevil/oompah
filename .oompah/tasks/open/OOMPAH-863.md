---
id: OOMPAH-863
type: bug
status: Open
priority: 1
title: Clear stale standalone Ready capacity alerts after a concurrent slot winner
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T17:58:24.963566Z'
updated_at: '2026-08-06T18:00:09.112372Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-863
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7752a9d697051b42829f41131d2549044bd68bcdf9b08358058a2e1bdc27616b
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 65e52117-c8f9-44db-ae90-514b58c5afef
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T17:59:53.593591+00:00'
  claim_expires_at: '2026-08-06T18:29:53.593591+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4990960f-8eab-446d-879b-fddea35c4e02
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-863
---
## Summary

Live deterministic reproduction while validating OOMPAH-851: two concurrent _reconcile_standalone_ready_to_integrate_tasks sweeps run with max_in_flight_prs=1. Durable reservation correctly permits only one review, but the losing sweep can arm standalone_ready_delivery for the same task after the winner creates or adopts its review. The dashboard then reports that the already-delivering task is waiting for capacity until a later sweep clears the row. This is a truthful-state/authority race, not normal capacity backpressure. Implementation scope: bind capacity-alert arm and clear to the exact standalone delivery authority, durable reservation, review identity, accepted head, and generation under the existing project/task synchronization or an equivalent CAS. A losing or stale sweep must refresh canonical review/reservation state immediately before publishing a wait alert; a winner must clear the same-task alert atomically with review creation/adoption. Preserve real capacity alerts for other waiting tasks, FIFO/priority ordering, one-review capacity, exact-head fencing, restart recovery, webhook lag handling, and failed-review-create diagnostics. Relevant code: Orchestrator._reconcile_standalone_ready_to_integrate_tasks, standalone delivery authority/reservation helpers, review creation/adoption, alert projection, and tests/test_standalone_ready_to_integrate.py. Required tests: deterministic barrier reproduction of two sweeps for the same task, repeated under load; two-task contention where the genuine loser remains informational; existing-review adoption; review-create failure; review close/release; restart between reservation and alert publication; and websocket/state snapshots. Acceptance criteria: once a concurrent winner creates or adopts the task review, the same response generation and every later snapshot contain no capacity-wait alert for that task; genuine waiting tasks remain truthful; exactly one review is created; stale callbacks cannot re-arm the alert; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 18:00
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
