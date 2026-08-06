---
id: OOMPAH-848
type: bug
status: Open
priority: 1
title: Isolate free-tier budget snapshot tests from heavyweight live state
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:35:27.470578Z'
updated_at: '2026-08-06T04:40:18.214105Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-848
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2b726a5ec2c196022230a244f15350ffc8de6ac84acf9ae25312ca06f007ff39
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 872590ea-9381-4f68-b15c-c5956fb8dd17
  claim_owner: 11468835-7c49-48df-a46d-b143af3a940a
  claimed_at: '2026-08-06T04:39:52.426319+00:00'
  claim_expires_at: '2026-08-06T05:09:52.426319+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 59d7e31e-c94e-4d3f-a00d-1475abe0cf6f
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-848
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-848
  base_branch: epic-OOMPAH-763
  base_sha: 93cc4c85664bfba06c82ac04ab66329c7f378832
  updated_at: '2026-08-06T04:40:10.052323+00:00'
---
## Summary

Regression evidence: the authoritative OOMPAH-791 exact-head gate at 0b5b039a reached 16,192 passes before tests/test_budget_free_tier_dispatch.py::TestGetSnapshotFreeTierActive::test_should_dispatch_increments_and_snapshot_reflects_it failed while unrelated worker test commands were concurrently bypassing the validation-resource lease. The test exercises only the free-tier counter and snapshot projection, yet it constructs a full Orchestrator and calls the complete get_snapshot path twice. Implementation scope: reproduce and identify whether construction or snapshot collection crosses unrelated storage, terminal-audit, maintenance, SCM, or corpus paths; isolate this unit test and adjacent free-tier snapshot tests from those dependencies without weakening the free-tier counter assertion or changing production semantics. If production get_snapshot contains avoidable unbounded synchronous work, move that work behind cached/bounded projections with explicit failure behavior. Relevant files: tests/test_budget_free_tier_dispatch.py, oompah/orchestrator.py snapshot/budget projection, and shared test helpers. Required tests: the named test repeatedly in serial and four-way concurrency, the complete budget module serial and -n 4, explicit assertions that unrelated live-state collectors are not invoked, and make test at the exact review head. Acceptance criteria: _should_dispatch still increments exactly once for an eligible free provider after budget exhaustion; the snapshot immediately reports free_tier_active and the counter; the unit test has no unrelated external/corpus dependency; it passes deterministically under a saturated canonical gate; no global timeout is raised.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 04:40
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 04:40
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
