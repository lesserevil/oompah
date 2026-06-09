---
id: TASK-473.1
title: Profile request latency under load to confirm the true bottleneck
status: Backlog
assignee: []
created_date: '2026-06-09 04:19'
labels:
  - 'needs:backend'
  - performance
dependencies: []
parent_task_id: TASK-473
priority: high
ordinal: 199000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Before optimizing, profile end-to-end request/WebSocket latency under realistic load to confirm where time actually goes (HTTP layer vs orchestrator vs subprocess/LLM). Use scripts/bench_server.py plus a mixed real-workload scenario. Output guides the rest of this epic.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Documented latency breakdown under load (HTTP vs orchestrator vs blocking calls)
<!-- AC:END -->
