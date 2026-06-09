---
id: TASK-473.4
title: 'Spike: split orchestrator into its own process behind a queue/IPC'
status: Backlog
assignee: []
created_date: '2026-06-09 04:20'
labels:
  - 'needs:backend'
  - performance
  - spike
dependencies: []
parent_task_id: TASK-473
priority: low
ordinal: 202000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Evaluate decoupling the orchestrator from the web process: orchestrator runs standalone and the web layer subscribes (queue/IPC/pubsub) for WebSocket push. This removes the shared-loop coupling entirely and would unlock Granian multi-worker (workers>1). Produce a design recommendation and rough effort estimate; do not implement here.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Written design + tradeoffs + effort estimate for orchestrator/web process split
<!-- AC:END -->
