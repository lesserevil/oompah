---
id: TASK-99
title: Implement event-driven infrastructure
status: Done
assignee: []
created_date: 2026-03-08 20:10
updated_date: 2026-03-08 20:58
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-210
  state: closed
  parent_id: oompah-ky3
  dependencies: []
  branch_name: oompah-210
  target_branch: null
  url: null
  created_at: '2026-03-08T20:10:14Z'
  updated_at: '2026-03-08T20:58:29Z'
  closed_at: '2026-03-08T20:58:29Z'
parent: TASK-71
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Set up an event-driven system within the app
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 26daac5e-0e4b-4a77-97ae-3dfe4b45c117
author: oompah
created: 2026-03-08T20:25:15Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 71f8e0f3-16e3-451c-8e35-8e3f30170e38
author: oompah
created: 2026-03-08T20:25:16Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d9aebc21-61e5-4f3c-afe3-41b060e00d4b
author: oompah
created: 2026-03-08T20:26:08Z

I understand the issue: This task is part of the 'All actions must be event driven' epic (oompah-ky3). The goal is to implement an internal event-driven infrastructure within the app — no external queuing systems. Currently, the orchestrator has ad-hoc observer patterns (_observers, _state_only_observers, _activity_observers lists). My plan: 1) Create an EventBus class in oompah/events.py with typed events, subscribe/emit/unsubscribe, and async support. 2) Define a set of standard event types (agent_dispatched, agent_completed, agent_failed, issue_state_changed, orchestrator_paused, etc.). 3) Wire the orchestrator to use EventBus internally instead of direct observer list mutations. 4) Write comprehensive unit tests in tests/test_events.py. This keeps all event handling in-app with no external dependencies.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3dd0abd7-6089-43d2-9d1c-5216d8b993ad
author: oompah
created: 2026-03-08T20:26:25Z

Discovery: The current observer pattern uses three raw lists (_observers, _state_only_observers, _activity_observers) in the orchestrator with direct callbacks. The server.py registers callbacks by appending to these lists. This works but is ad-hoc — there's no event typing, no ordering guarantees, no easy way to add new event types without modifying the observer interface. I'll implement a proper EventBus (in oompah/events.py) with: typed event constants, sync+async handler support, subscribe/unsubscribe, and error isolation per handler. The orchestrator will use the EventBus internally while maintaining backward compatibility via the existing observer list interface.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1b7a0831-6e77-4dd2-91b6-02c7bcef9ffa
author: oompah
created: 2026-03-08T20:29:33Z

Agent failed: HTTP 429 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"{'error': 'Priority-based rate limit exceeded. Priority: dev, Rate limit type: tokens, Remaining: -1287005, Model saturation: 70.7%'}","type":"None","param":"None","code":"429"}}. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4c814089-203b-4783-8e7e-f4dd9ddd0bc7
author: oompah
created: 2026-03-08T20:29:43Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 29ac0a65-56f9-41c2-90f4-0187c96b4b95
author: oompah
created: 2026-03-08T20:29:44Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ff10d315-e684-4994-a5ef-b9c873831861
author: oompah
created: 2026-03-08T20:29:45Z

Agent failed: HTTP 429 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"{'error': 'Priority-based rate limit exceeded. Priority: dev, Rate limit type: tokens, Remaining: -894486, Model saturation: 72.9%'}","type":"None","param":"None","code":"429"}}. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1e03dd06-ed0f-4511-a6fe-5cbf5190645f
author: oompah
created: 2026-03-08T20:30:06Z

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 602caf78-90ae-4a64-aaa9-46bb76df8ecf
author: oompah
created: 2026-03-08T20:30:07Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4985ebf1-a224-4751-9355-5f0f7ed92266
author: oompah
created: 2026-03-08T20:31:02Z

Continuation run: Previous agent had the right plan but was rate-limited. I've reviewed the codebase. The orchestrator uses 3 raw observer lists (_observers, _state_only_observers, _activity_observers). My plan: 1) Create oompah/events.py with EventBus class supporting typed events, subscribe/unsubscribe, sync+async dispatch with error isolation. 2) Wire orchestrator to use EventBus internally while maintaining backward compat via existing observer lists. 3) Write comprehensive tests in tests/test_events.py. Pre-existing test failures noted (not caused by my changes).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 12976518-d76d-4d8d-9b9c-cc4617a35410
author: oompah
created: 2026-03-08T20:50:04Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f5f32aff-002a-44df-b082-13615f2ae4af
author: oompah
created: 2026-03-08T20:50:04Z

Focus: DevOps Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8ec3c384-3c8c-4903-8211-cc265ea1cf75
author: oompah
created: 2026-03-08T20:50:56Z

I understand the issue: This task is part of the 'All actions must be event driven' epic. Previous agents have already done deep analysis. My plan: 1) Create oompah/events.py with an EventBus class (typed events, subscribe/emit/unsubscribe, sync+async dispatch, error isolation per handler). 2) Integrate the EventBus into the Orchestrator as a replacement for the three raw observer lists. 3) Update server.py to subscribe via the EventBus. 4) Write comprehensive tests in tests/test_events.py. The pre-existing test failures (test_collapsed_epics, test_draft_epic_swimlane, test_focus) are unrelated to this change.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 70775879-f203-43d2-99ff-daf53b1c4418
author: oompah
created: 2026-03-08T20:56:48Z

Implementation complete. Created oompah/events.py with EventBus class (typed EventType enum, sync emit(), async emit_async(), subscribe/unsubscribe/unsubscribe_all, error isolation per handler, idempotent subscription). Integrated EventBus into Orchestrator: added event_bus attribute, emits AGENT_DISPATCHED on dispatch, ORCHESTRATOR_PAUSED/RESUMED on pause/unpause, ORCHESTRATOR_TICK/_STATE_UPDATED/AGENT_ACTIVITY on every notify, AGENT_COMPLETED/FAILED/STALLED/MAX_TURNS on worker exit, ISSUE_RETRY_SCHEDULED on retry scheduling. Legacy _observers lists kept for backward compat with server.py. Tests: 41 new tests in tests/test_events.py covering all event bus operations and orchestrator integration.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 47f1f44c-2413-4442-bc46-b9bad0c933f7
author: oompah
created: 2026-03-08T20:56:56Z

Verification: 41/41 new tests pass. Pre-existing failures (test_collapsed_epics, test_draft_epic_swimlane, test_focus) unchanged — these are unrelated to the event-driven infrastructure. All previously passing tests still pass (703 total).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a08cd16e-2a4d-489b-abe4-5f5542ce699a
author: oompah
created: 2026-03-08T20:58:24Z

PR created: https://github.com/lesserevil/oompah/pull/38

Delivered:
- oompah/events.py: EventBus with typed EventType enum (13 event types), sync/async dispatch, error isolation, idempotent subscription
- oompah/orchestrator.py: EventBus wired in — emits typed events at all agent/orchestrator lifecycle points; legacy observer lists preserved for backward compat
- tests/test_events.py: 41 tests, all passing

The EventBus is the foundation for future replacement of polling patterns (as required by oompah-ky3). External consumers can now subscribe to AGENT_DISPATCHED, AGENT_COMPLETED, etc. without modifying orchestrator internals.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 577a2ab9-d009-48d2-933a-1325d8b04e78
author: oompah
created: 2026-03-08T20:58:30Z

Agent completed successfully in 507s (4452684 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
