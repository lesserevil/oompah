---
id: TASK-465.4
title: Wake dispatch loop when graceful restart finishes draining
status: Open
assignee: []
created_date: '2026-06-08 19:51'
updated_date: '2026-06-08 19:51'
labels:
  - bug
dependencies: []
parent_task_id: TASK-465
priority: high
ordinal: 165000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During live recovery on 2026-06-08, POST /api/v1/orchestrator/restart saved undrained restart_issues and set _stopping=True, but the main event-driven dispatch loop was blocked on _dispatch_queue.get() and did not wake to exit/re-exec. The old process kept serving port 8090 until manually killed.

Fix graceful_restart so it wakes the run loop after setting _stopping, or otherwise cancels/interrupts the queue wait deterministically. Add a regression test that starts the event-driven loop, invokes graceful_restart with an undrained running task, and proves _run returns wants_restart=True without requiring another external event.

Acceptance criteria:
- Graceful restart exits/re-execs after the drain timeout even when the dispatch queue is idle.
- Undrained tasks are persisted for restart recovery exactly once.
- Tests cover the idle-queue drain-complete case.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:51
---
Filed from live recovery: graceful restart saved restart_issues but left the event-driven loop blocked on the dispatch queue.
---
<!-- COMMENTS:END -->
