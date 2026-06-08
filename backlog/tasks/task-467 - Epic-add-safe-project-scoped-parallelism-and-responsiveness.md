---
id: TASK-467
title: 'Epic: add safe project-scoped parallelism and responsiveness'
status: Backlog
assignee: []
created_date: '2026-06-08 18:48'
labels:
  - epic
  - tick-latency
  - dispatch-performance
  - responsiveness
dependencies: []
references:
  - oompah/orchestrator.py
  - oompah/server.py
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - tests
priority: 0
ordinal: 10
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Parallelize independent project-scoped fetch and maintenance work without risking duplicate dispatch, tracker write races, or git checkout corruption. Keep the dashboard and WebSocket state responsive during long background jobs, and make long-running work visible to operators.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Project-scoped work uses locks around tracker writes and git mutations.
- [ ] #2 Independent project fetches and maintenance jobs can run concurrently within configured bounds.
- [ ] #3 Dashboard state requests stay responsive while maintenance is running.
<!-- AC:END -->
