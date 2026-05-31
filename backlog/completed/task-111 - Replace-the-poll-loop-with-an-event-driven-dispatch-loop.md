---
id: TASK-111
title: Replace the poll loop with an event-driven dispatch loop
status: Done
assignee: []
created_date: 2026-03-08 21:18
updated_date: 2026-03-08 22:50
labels:
- archive:yes
- draft
- merge-conflict
- merged
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-k3d.3
  state: closed
  parent_id: oompah-k3d
  dependencies: []
  branch_name: oompah-k3d.3
  target_branch: null
  url: null
  created_at: '2026-03-08T21:18:44Z'
  updated_at: '2026-03-08T22:50:56Z'
  closed_at: '2026-03-08T22:50:56Z'
parent: TASK-108
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Replace the poll loop with an event-driven dispatch loop
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: b04561d8-f27c-4b41-ab5f-ebc525efc608
author: oompah
created: 2026-03-08T21:19:04Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ca733df7-03e4-4264-9374-559ec5426ff0
author: oompah
created: 2026-03-08T21:19:04Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 641934fc-8aeb-4247-9084-404eab5ccc81
author: oompah
created: 2026-03-08T21:19:43Z

I understand the issue: Replace the poll-based run() loop in orchestrator.py with an event-driven dispatch loop. Currently, the run() method polls every 30s (poll_interval_ms) triggering a full _tick() world scan. The target is an asyncio.Queue-based dispatch loop where the orchestrator blocks waiting for events, runs targeted handlers based on event type, and keeps a safety-net full sync at a longer interval (5-10 min).

My plan:
1. Add an OrchestratorEvent dataclass and DispatchEventType enum to describe what triggered an action
2. Add an internal asyncio.Queue for events (dispatch_queue)
3. Add a full_sync_interval_ms config field (default 300s = 5min) as the safety-net interval
4. Replace run() poll loop with an event-driven loop that awaits queue events
5. Keep _tick() as the safety-net full sync; add targeted handlers for specific events
6. Agent lifecycle events, refresh requests, and retry timers all post to the queue
7. Keep backward compatibility - poll_interval_ms becomes the safety-net interval if full_sync_interval_ms not set
8. Write tests covering the new event-driven loop behavior
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 14b6fdb8-adfc-4e26-b69e-b6e50b649e4c
author: oompah
created: 2026-03-08T21:21:23Z

Found the key code: The run() loop in orchestrator.py:328 is the poll-based loop. It runs _tick() then waits on _refresh_requested event with timeout=poll_interval_ms. The plan is to:
1. Add full_sync_interval_ms to ServiceConfig (default 300000 = 5min)
2. Add _dispatch_queue: asyncio.Queue to Orchestrator
3. Add DispatchEvent dataclass for typed events
4. Replace run() loop with event-driven loop
5. Have _on_worker_exit, request_refresh, _on_retry_timer, and unpause all post to the queue
6. Safety-net full sync runs when time_since_last_full_sync > full_sync_interval_ms
7. The poll_interval_ms config becomes the safety-net interval
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 850dd558-c66a-40f1-ac4e-b2789f153d31
author: oompah
created: 2026-03-08T22:06:53Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bc58de3a-9d8e-4480-8ee2-53aa1b3bcb9b
author: oompah
created: 2026-03-08T22:06:54Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2f3777f8-5467-4fa1-a7f5-e2952289c6e3
author: oompah
created: 2026-03-08T22:08:12Z

I understand the issue and the existing context from prior agents. The current run() loop polls every poll_interval_ms (30s default) triggering a full _tick() world scan. The goal is to replace this with an event-driven dispatch loop that blocks on an asyncio.Queue, handles targeted events, and only runs a full _tick() as a safety-net at a longer interval (full_sync_interval_ms, default 300s).

My implementation plan:
1. Add DispatchEventType enum and DispatchEvent dataclass
2. Add full_sync_interval_ms to ServiceConfig (default 300000ms = 5min)
3. Add _dispatch_queue: asyncio.Queue[DispatchEvent] to Orchestrator
4. Add a _post_event() method to put events on the queue
5. Replace the run() poll loop with an event-driven loop that awaits queue events
6. Have _on_worker_exit, unpause, request_refresh, and _on_retry_timer all post events to the queue
7. Keep _tick() for the safety-net full sync
8. Add a background task that posts FULL_SYNC events at the full_sync_interval_ms cadence
9. Write comprehensive tests for the new event-driven loop
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: acf1b4d4-fb7c-4621-942d-56864303ea25
author: oompah
created: 2026-03-08T22:16:50Z

Implementation complete. Changes made:

1. **oompah/config.py**: Added full_sync_interval_ms field (default 300000ms = 5min) to ServiceConfig, parsed from polling.full_sync_interval_ms in WORKFLOW.md front matter.

2. **oompah/orchestrator.py**:
   - Added DispatchEventType enum (WORKER_EXIT, REFRESH_REQUESTED, RETRY_FIRED, FULL_SYNC)
   - Added DispatchEvent dataclass with event_type, issue_id, and payload fields
   - Added _dispatch_queue: asyncio.Queue[DispatchEvent] to __init__
   - Added _post_event() helper that puts events on the queue
   - Added _full_sync_loop() background task that posts FULL_SYNC events at full_sync_interval_ms cadence
   - Replaced the poll-based run() loop with an event-driven loop that:
     - Runs an initial _tick() on startup
     - Starts _full_sync_loop() as a background task
     - Blocks on _dispatch_queue.get() instead of sleeping poll_interval_ms
     - Calls _tick() for each dequeued event
     - Stops cleanly when _stopping is set
   - Updated unpause() to post REFRESH_REQUESTED event (kept legacy _refresh_requested.set() for compat)
   - Updated request_refresh() to post REFRESH_REQUESTED event
   - Updated _on_worker_exit() to post WORKER_EXIT event after handling completion
   - Updated _on_retry_timer() to post RETRY_FIRED event when a retry fires

3. **tests/test_event_driven_loop.py**: 32 new tests covering all new behavior.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7e7135d0-ce98-4df0-8530-c34998ebff67
author: oompah
created: 2026-03-08T22:17:19Z

Verification: All 827 tests pass (795 pre-existing + 32 new). No regressions. Key test assertions: (1) loop blocks on queue not sleep, (2) _tick() called per event, (3) worker exit/unpause/request_refresh/retry_timer all post to queue, (4) full_sync_loop fires FULL_SYNC at configured interval, (5) old poll_interval_ms sleep no longer drives the loop (tested by showing <= 3 ticks in 300ms with 50ms old interval).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 88825f9e-23f7-445a-bab2-234dc3c78c6c
author: oompah
created: 2026-03-08T22:30:17Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b71c505d-ecea-4e19-ae4d-596bb2ee9747
author: oompah
created: 2026-03-08T22:30:17Z

Agent failed: Agent process exited. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 114f29ce-daa7-4af9-b646-0dd053069b60
author: oompah
created: 2026-03-08T22:30:18Z

Agent failed: Agent process exited. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8d154fd0-3d70-4a40-81f4-5eb8d447059e
author: oompah
created: 2026-03-08T22:30:18Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6bab3de9-aa64-4ec8-9136-bb9e485e4a21
author: oompah
created: 2026-03-08T22:30:19Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6d5fe62a-627e-4ad0-98a3-308d5c24f085
author: oompah
created: 2026-03-08T22:30:19Z

Agent failed: Agent process exited. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0cb04cf7-beff-47fa-9801-bc11f0ec7f5e
author: oompah
created: 2026-03-08T22:37:12Z

Completion summary: The event-driven dispatch loop is fully implemented and all 919 tests pass.

**What was delivered:**

1. **DispatchEventType enum** (WORKER_EXIT, REFRESH_REQUESTED, RETRY_FIRED, FULL_SYNC) - type-safe event categories

2. **DispatchEvent dataclass** - carries event_type, optional issue_id, and payload

3. **_dispatch_queue: asyncio.Queue** - the queue that drives the event-driven loop

4. **_post_event()** - non-blocking helper to enqueue events

5. **_full_sync_loop()** - background task posting FULL_SYNC events at full_sync_interval_ms (default 300s)

6. **Event-driven run()** - replaces old poll loop:
   - Runs startup tick immediately
   - Blocks on queue.get() waiting for events
   - Calls _tick() per event (not per timer interval)
   - Logs 'Safety-net full sync triggered' when interval elapses
   - Updates _last_full_sync after each tick

7. **_full_sync_due()** - predicate for safety-net interval

8. **_last_full_sync** - monotonic timestamp of last full tick

9. **Event posting** in unpause(), request_refresh(), _on_worker_exit(), _on_retry_timer()

10. **Refactored _tick()** delegates to _handle_reconcile(), _handle_review_check(), _handle_dispatch_needed(), _handle_yolo_review(), _handle_auto_update() (merged from upstream partial implementation)

11. **32 new tests** in test_event_driven_loop.py

**Key behavior change:** Orchestrator no longer wakes up every 30s unconditionally. It now wakes up only when something actually happened (agent exit, user request, retry timer, full sync interval).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 74f749c8-c73e-43e8-ac56-426922952bec
author: oompah
created: 2026-03-08T22:37:41Z

Agent completed successfully in 1848s (11318392 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ea4a4c2a-8d43-4ae2-bfce-db44354e477f
author: oompah
created: 2026-03-08T22:37:44Z

Review created: https://github.com/lesserevil/oompah/pull/44
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 257bffb7-a39b-4a89-8218-113509adaa12
author: oompah
created: 2026-03-08T22:38:31Z

YOLO: Merge conflict detected on review #44. Rebase onto main and resolve conflicts.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 31c8dd5b-45f8-4710-9a2f-5be7dcaa17f7
author: oompah
created: 2026-03-08T22:39:57Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 84162b69-5c77-4463-90b7-4bd8c2a91fb4
author: oompah
created: 2026-03-08T22:39:58Z

Focus: Merge Conflict Resolver
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: fbf614eb-ba35-4bae-9f68-6733197f5fc8
author: oompah
created: 2026-03-08T22:42:33Z

I understand the conflict: The oompah-k3d.3 branch modified tests/test_orchestrator_merged.py to use _unmerged_review_branches (keeping _merged_branches assignments). Meanwhile, main (df3ffb9) has a different version of the same file that uses _blocker_has_unmerged_review + _unmerged_review_branches but WITHOUT _merged_branches. The branch's orchestrator.py uses _blocker_has_unmerged_pr method (renamed from _blocker_has_unmerged_review). I need to rebase and resolve so tests match the actual implementation in oompah-k3d.3's orchestrator.py.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a039e47b-4be0-46ab-8e9b-da90b3fdeb6e
author: oompah
created: 2026-03-08T22:45:59Z

Found conflict details: tests/test_orchestrator_merged.py has 5 conflict markers. The branch (oompah-k3d.3) added _merged_branches assignments to tests, used _blocker_has_unmerged_pr. Main (df3ffb9) uses _blocker_has_unmerged_review without _merged_branches. The current orchestrator.py uses _blocker_has_unmerged_pr. Correct resolution: keep the branch's content (_merged_branches + _blocker_has_unmerged_pr) since that matches what oompah-k3d.3 introduced.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: beb3f43b-f31c-4b20-b72c-00e4407fc969
author: oompah
created: 2026-03-08T22:49:58Z

Implementation complete: Resolved conflict in tests/test_orchestrator_merged.py. The conflict was between main's version (using _blocker_has_unmerged_review without _merged_branches) and branch's version (using _blocker_has_unmerged_pr with _merged_branches). Kept branch's content since oompah-k3d.3 renamed the method to _blocker_has_unmerged_pr and added _merged_branches test coverage. Rebased onto origin/main (df3ffb9), force-pushed.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: db612973-7bda-4a3b-9ae9-7c2e6121bedb
author: oompah
created: 2026-03-08T22:50:26Z

Verification: All 980 tests pass after rebase (980 passed, 10 warnings in 7.66s). No regressions. The test_orchestrator_merged.py, test_event_driven_loop.py, and test_orchestrator_full_sync.py all pass correctly.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ee43366b-7770-4e50-b9dd-7eaf7c708dd5
author: oompah
created: 2026-03-08T22:50:31Z

Completion: Merge conflict resolved. Branch oompah-k3d.3 successfully rebased onto origin/main (df3ffb9). Single conflict in tests/test_orchestrator_merged.py resolved by preserving both branches' intent: method renamed to _blocker_has_unmerged_pr and _merged_branches test data retained from the feature branch. Force-pushed to origin/oompah-k3d.3. All 980 tests pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 13a8b97c-052b-495b-a3fc-b2c662ec2d33
author: oompah
created: 2026-03-08T22:50:56Z

Agent completed successfully in 659s (994613 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
