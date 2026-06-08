---
id: TASK-465.1
title: Add fine-grained orchestrator tick telemetry
status: Open
assignee: []
created_date: '2026-06-08 18:47'
labels:
  - task
  - tick-latency
  - dispatch-performance
  - 'needs:backend'
  - 'needs:test'
dependencies: []
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-465
priority: 0
ordinal: 2
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Instrument _tick() and _handle_dispatch_needed() with substep timings so slow-tick logs and state snapshots show exactly where time is spent. Break dispatch timing into candidate fetch, blocker pre-resolution, duplicate detection, candidate selection, normal dispatch, epic planning, epic close/PR maintenance, staleness checks, rebase filing, orphan reset, watchdog, and repo self-heal. Keep log volume bounded and avoid exposing secrets in snapshots.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Slow-tick log output reports nested dispatch substep timings instead of one aggregate dispatch number.
- [ ] #2 State snapshots expose recent tick timing summaries suitable for the dashboard without secrets.
- [ ] #3 Tests cover timing collection and verify disabled or missing timings do not break existing snapshots.
<!-- AC:END -->
