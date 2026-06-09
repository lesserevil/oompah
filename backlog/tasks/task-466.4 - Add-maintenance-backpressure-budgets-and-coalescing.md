---
id: TASK-466.4
title: Add maintenance backpressure budgets and coalescing
status: Open
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-08 22:50'
labels:
  - task
  - tick-latency
  - maintenance
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-466.2
  - TASK-466.3
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-466
ordinal: 9
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add scheduling controls so maintenance jobs cannot starve dispatch: per-job minimum interval, max runtime or item budget, in-flight coalescing, skip counters, and explicit next-run timestamps. The scheduler should drop redundant maintenance requests while one is running and should record when a job is skipped because dispatch is busy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A long maintenance job cannot launch duplicate copies of itself.
- [ ] #2 Maintenance jobs enforce configured or hard-coded safety budgets and resume on a later run.
- [ ] #3 State snapshots include enough maintenance lane status to diagnose skipped, running, failed, and completed jobs.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:51
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 19:58
---
Understanding: TASK-466.4 requires adding systematic scheduling controls for maintenance jobs in orchestrator.py. The current code has ad-hoc per-job throttle timestamps (_last_auto_archive_monotonic, _last_repo_heal, _last_watchdog_run) but no unified system for in-flight coalescing, skip counters, item budgets, or observability.\n\nPlan: (1) Add MaintenanceJobState dataclass to track per-job state (in_flight, skip_count, run_count, last_status, next_run_monotonic, last_duration_s). (2) Add _run_maintenance_job() gate method on Orchestrator that handles coalescing, throttling, and state tracking. (3) Wire existing maintenance methods through the new gate. (4) Add maintenance_lane section to get_snapshot(). (5) Write comprehensive tests covering: coalescing, interval throttle, skip counters, status transitions, and snapshot observability.
---
<!-- COMMENTS:END -->
