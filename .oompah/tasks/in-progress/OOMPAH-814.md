---
id: OOMPAH-814
type: task
status: In Progress
priority: null
title: Make submit-queue dispatch fixtures deterministic under full-gate load
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T23:55:41.082395Z'
updated_at: '2026-08-05T00:04:27.777463Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Exact full-gate reproduction on OOMPAH-807 at 069633eeb: 15,709 tests passed, but tests/test_submit_queue_concurrency.py::TestShouldDispatchOpenReviewGate::test_cap3_two_open_dispatches exceeded the global five-second timeout while unittest.mock dynamically created an unset Project.default_branch child inside Orchestrator._new_tracker_for_project. Isolated exact test, full module serial/xdist, and 40 concurrent process repetitions pass, proving a load-sensitive incomplete fixture rather than the asserted review-cap behavior. Implementation scope: make the test project/tracker fixture concrete and complete for every attribute the dispatch path reads, avoid dynamic MagicMock child creation and accidental real tracker construction, and close any orchestrator-owned resources. Audit neighboring submit-queue fixtures for the same incomplete project double without weakening dispatch assertions or increasing the global timeout. Required tests: exact test repeated under parallel load, complete test_submit_queue_concurrency serial and xdist, relevant dispatch/tracker factory tests, terminal mutation scan, and exact server full gate. Acceptance: review-cap assertions exercise only dispatch policy, never instantiate a real tracker or synthesize mock attributes, and stay below the lifecycle timeout under full-suite load.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 23:56
---
Claimed implementation in /home/shedwards/.oompah/worktrees/oompah/OOMPAH-814 on epic-OOMPAH-763--task-OOMPAH-814 at exact parent 30dc2b2075a48c6c542da55a46ad0285f492d527. Reproducing the submit-queue fixture path and auditing neighboring project/tracker doubles before a tests-only patch; submission and owner-claim release remain with the landing coordinator.
---
author: oompah
created: 2026-08-05 00:03
---
Implemented deterministic submit-queue fixtures: real Project and ProjectStore objects replace incomplete MagicMock project/store doubles, Orchestrator construction is bounded by concrete no-I/O tracker instances, and every helper-owned executor/store plus the API TestClient is closed. Added regression proving an unset default_branch cannot invoke _new_tracker_for_project during _should_dispatch. Checks passed: exact regression + original failure (2), full module serial (62), full module xdist -n4 (62), 40 repetitions in 8 concurrent processes, related tracker factory tests (12), and make terminal-audit-scan. Preparing the commit/push; exact server full gate and task submission remain with the landing coordinator.
---
author: oompah
created: 2026-08-05 00:04
---
Implementation handoff is pushed at cb1446d4beba7ad83a1b67d94574ad5c01cf8814 on epic-OOMPAH-763--task-OOMPAH-814 (exact base 30dc2b2075a48c6c542da55a46ad0285f492d527). Branch is clean and up to date with origin. Focused verification remains green: module serial 62/62, module xdist -n4 62/62, related tracker factory tests 12/12, 40 concurrent repetitions, terminal mutation scan. Per coordination instructions, I did not submit OOMPAH-814 or release its owner claim; landing coordinator should land this ahead of rebasing OOMPAH-807 and run the exact server full gate.
---
<!-- COMMENTS:END -->
