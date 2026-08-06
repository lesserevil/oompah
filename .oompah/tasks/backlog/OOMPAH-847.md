---
id: OOMPAH-847
type: bug
status: Backlog
priority: 1
title: Isolate dispatch-lock and epic-review unit tests from unrelated loaded-gate
  work
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T04:13:46.553414Z'
updated_at: '2026-08-06T04:13:46.553414Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

The OOMPAH-831 exact combined-tree gate at head 93b0295bc passed 16,085 tests and then failed tests/test_dispatch_lane_contract.py::TestDispatchLockExceptionSafety::test_second_dispatch_succeeds_after_first_raises and tests/test_epic_strategy.py::TestOpenEpicMainPrs::test_existing_pr_waits_for_changed_head_quality_gate during a 1,041-second saturated run. Neither test exercises OOMPAH-831 auditor code. The dispatch-lock test lets the second call traverse unrelated audit/duplicate-preflight scheduling; the epic-review test persists an unasserted review-capacity adoption before checking its mocked gate result. Concurrent worker commands were also proven to bypass OOMPAH-816 resource leasing (tracked separately in OOMPAH-846). Implementation scope: obtain exact failure classification with isolated and loaded reproductions; remove unrelated real tracker/store/executor/network/background work from both unit tests while keeping production semantics and assertions strict; add deterministic cleanup for any owned executor/store/event-loop resources; use a scoped bounded timeout only if the intended operation itself legitimately needs loaded-gate headroom. Do not raise the global timeout or mask semantic failures. Required tests: both exact nodes repeated concurrently; complete dispatch-lane and epic-strategy modules; an ordering/leakage sequence that proves no background work crosses tests; canonical make test at the review head. Acceptance: both tests assert only lock exception safety or changed-head gate behavior, fail when that contract regresses, exit with no live background work, and pass reliably in a saturated exact gate.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

