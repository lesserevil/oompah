---
id: TASK-467.2
title: Bound and parallelize project-scoped refresh work
status: Open
assignee: []
created_date: '2026-06-08 18:48'
labels:
  - task
  - tick-latency
  - dispatch-performance
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-467.1
  - TASK-465.1
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-467
priority: 0
ordinal: 12
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Refactor candidate fetch, running-state refresh, review fetch, merged-branch fetch, and maintenance project scans to use bounded per-project concurrency with timeouts and stale-cache fallback. The dispatch lane should use the freshest complete data available while avoiding one slow project blocking all other projects.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A slow or wedged project refresh does not block dispatch for unrelated projects after its timeout.
- [ ] #2 Review/open-PR gating remains conservative when refresh data is stale or unavailable.
- [ ] #3 Per-project refresh timings and timeout counts are visible in diagnostics.
<!-- AC:END -->
