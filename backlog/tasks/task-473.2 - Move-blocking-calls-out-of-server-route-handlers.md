---
id: TASK-473.2
title: Move blocking calls out of server route handlers
status: Backlog
assignee: []
created_date: '2026-06-09 04:19'
labels:
  - 'needs:backend'
  - performance
dependencies: []
parent_task_id: TASK-473
priority: medium
ordinal: 200000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Audit the ~11 subprocess/run_in_executor/sync-I/O sites in oompah/server.py route handlers and ensure blocking work runs off the event loop (threadpool/async), so it cannot stall the shared loop the orchestrator and WebSocket broadcasts depend on.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 No synchronous blocking call runs inline on the event loop in hot route handlers
<!-- AC:END -->
