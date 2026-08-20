---
id: OOMPAH-1267
type: task
status: Open
priority: null
title: Make restart replacement rollback test deterministic under concurrent gates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-14T08:43:25.263614Z'
updated_at: '2026-08-20T23:14:52.764596Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 74c46553-2c2b-43cf-a780-9f13e770c900
  request_fingerprint: c93c49f73d14f0dbd98db4eaf2f0bc6f44f4965a6f4e68ab29b4fa036d4eeecd
oompah.lifecycle_revision: 1
oompah.last_batch:
  batch_id: batch-41327bd44d2248989351b0a98c84746f
  actor: shedwards
  committed_at: '2026-08-18T16:18:18.970327Z'
  operation:
    kind: whole_column_move
    source_status: Backlog
    scope: flat_board
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d12a8b6a59aa90f19f4ddbe2f11d1a7a62462ddc8014f5351f2e7cbea8ac64b7
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 8a21f1023f935c5377428c7775977f7e12c636570efea22996843d91dd0644b8:56516
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-20T23:14:21.261962+00:00'
  claim_expires_at: '2026-08-20T23:44:21.261962+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a0bd438d-4957-45ba-a8cd-c652e69bc369
oompah.work_contributors:
  runs:
  - run_id: 671f8f5990b64a229b74342ef73ff72e--contributor-4256b9f40773
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-1267
    source_sha: null
    completed_at: ''
---
## Summary

Repeated concurrency bug: tests/test_restart_api.py::test_replacement_timeout_rolls_back_before_concurrent_replacement failed late in two independent full Makefile gates running concurrently on OOMPAH-1266 and OOMPAH-1249. Both branches are unrelated to restart lifecycle code; the exact test passes isolated and the full restart API file passes 33/33, proving the current synchronization/timeout contract is load-sensitive rather than deterministic. Diagnose the replacement-timeout/concurrent-replacement ordering and replace wall-clock/test-runner-load assumptions with explicit observable synchronization or a bounded state predicate. Preserve the production guarantee that a timed-out replacement rolls back before a concurrent replacement can acquire authority. Relevant context: tests/test_restart_api.py and restart replacement lifecycle/locking code. Required tests: deterministic interleavings for timeout-before-replacement and replacement-before-timeout, repeated/parallel execution under CPU load, no leaked lifecycle state or process, and focused restart plus full Makefile gate. Acceptance: the exact race test cannot fail solely because another quality gate is consuming the box, real ordering regressions still fail, and no timeout is simply widened to hide the race.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-20 23:14
---
Duplicate screening dispatched (profile: default, task remains Open)
---
<!-- COMMENTS:END -->
