---
id: TASK-465.3
title: Add regression coverage for tick lane serialization
status: In Progress
assignee: []
created_date: '2026-06-08 18:47'
updated_date: '2026-06-08 20:51'
labels:
  - task
  - tick-latency
  - dispatch-performance
dependencies:
  - TASK-465.2
references:
  - oompah/orchestrator.py
modified_files:
  - tests/test_orchestrator_handlers.py
  - tests/test_submit_queue_concurrency.py
parent_task_id: TASK-465
ordinal: 4
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add tests that prove full ticks do not overlap unsafely, dispatch selection is serialized, maintenance work can run without blocking eligible dispatch, and tick requests raised while maintenance is active are coalesced into the next safe dispatch pass.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A slow maintenance job does not prevent a ready Open task from being dispatched on the dispatch lane.
- [ ] #2 Two dispatch selection passes cannot claim the same issue.
- [ ] #3 Tests cover shutdown/restart behavior with maintenance jobs in flight.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:36
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 19:37
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-08 20:48
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:51
---
UNDERSTANDING: Investigating whether TASK-465.3 is a duplicate of TASK-465.2. TASK-465.2 (Done) implemented the dispatch lane contract and added 34 tests in test_dispatch_lane_contract.py. TASK-465.3 has different acceptance criteria: AC1 (maintenance doesn't block dispatch), AC2 (no double-dispatch), AC3 (shutdown with maintenance in flight). A prior Test Engineer agent already created tests/test_tick_lane_serialization.py (untracked, never committed) with 5 test classes covering all 3 ACs. The tests are distinct from TASK-465.2's tests — deeper regression coverage of run() sequential behavior, tick ordering, and shutdown safety. This is NOT a duplicate. Plan: run the tests, fix any failures, commit and push.
---
<!-- COMMENTS:END -->
