---
id: OOMPAH-850
type: bug
status: Archived
priority: 1
title: Isolate free-tier budget snapshot tests from heavyweight live state
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:36:39.542954Z'
updated_at: '2026-08-06T04:37:53.078597Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-9c8a6f94ea03
    project_id: proj-14849f1b
    task_id: OOMPAH-850
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d39ad1b8ccd066e9a1d770e800ec492c79798986fac1f10f906a7ee568ca5a18
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Operator cleanup of an accidental duplicate created in this session; no
      implementation or evidence exists on this task.
    created_at: '2026-08-06T04:37:47.834130+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Regression evidence: the authoritative OOMPAH-791 exact-head gate at 0b5b039a reached 16,192 passes before tests/test_budget_free_tier_dispatch.py::TestGetSnapshotFreeTierActive::test_should_dispatch_increments_and_snapshot_reflects_it failed while unrelated worker test commands were concurrently bypassing the validation-resource lease. The test exercises only the free-tier counter and snapshot projection, yet it constructs a full Orchestrator and calls the complete get_snapshot path twice. Implementation scope: reproduce and identify whether construction or snapshot collection crosses unrelated storage, terminal-audit, maintenance, SCM, or corpus paths; isolate this unit test and adjacent free-tier snapshot tests from those dependencies without weakening the free-tier counter assertion or changing production semantics. If production get_snapshot contains avoidable unbounded synchronous work, move that work behind cached/bounded projections with explicit failure behavior. Relevant files: tests/test_budget_free_tier_dispatch.py, oompah/orchestrator.py snapshot/budget projection, and shared test helpers. Required tests: the named test repeatedly in serial and four-way concurrency, the complete budget module serial and -n 4, explicit assertions that unrelated live-state collectors are not invoked, and make test at the exact review head. Acceptance criteria: _should_dispatch still increments exactly once for an eligible free provider after budget exhaustion; the snapshot immediately reports free_tier_active and the counter; the unit test has no unrelated external/corpus dependency; it passes deterministically under a saturated canonical gate; no global timeout is raised.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

