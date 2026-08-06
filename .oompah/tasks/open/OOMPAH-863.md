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
updated_at: '2026-08-06T18:01:19.468016Z'
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
  evidence: 'Required structural peers could not fit the bounded duplicate corpus.
    Omitted peer identifiers: OOMPAH-848, OOMPAH-849, OOMPAH-850, OOMPAH-851, OOMPAH-852,
    OOMPAH-853, OOMPAH-854, OOMPAH-855, OOMPAH-856, OOMPAH-858, OOMPAH-860, OOMPAH-861,
    OOMPAH-862.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 3
  retry_after: '2026-08-06T18:01:08.532080+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4990960f-8eab-446d-879b-fddea35c4e02
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-863
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-863
  base_branch: epic-OOMPAH-763
  base_sha: 0e0056375918977c9b0b2d59524ce8ae68ceee40
  updated_at: '2026-08-06T18:00:09.138430+00:00'
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 2914
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 2914
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 2914
    cost_usd: 0.0
    recorded_at: '2026-08-06T18:01:08.530869+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-863__20260806T180027Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-863
    source_sha: 0e0056375918977c9b0b2d59524ce8ae68ceee40
    completed_at: '2026-08-06T18:01:08.552372+00:00'
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
author: oompah
created: 2026-08-06 18:00
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 18:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 2.9K out [2.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 7s
- Log: OOMPAH-863__20260806T180027Z.jsonl
---
<!-- COMMENTS:END -->
