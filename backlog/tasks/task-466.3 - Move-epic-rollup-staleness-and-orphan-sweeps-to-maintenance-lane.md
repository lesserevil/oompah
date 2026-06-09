---
id: TASK-466.3
title: Move epic rollup staleness and orphan sweeps to maintenance lane
status: Open
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-08 22:50'
labels:
  - task
  - tick-latency
  - maintenance
  - epic
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-466.1
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_epic_strategy.py
  - tests/test_epic_rebase_state.py
parent_task_id: TASK-466
ordinal: 8
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move auto-close completed epics, epic-to-main PR opening, epic staleness checks, proactive rebase filing, stale epic rebase pruning, watchdog scans, and orphaned In Progress resets into bounded maintenance jobs. Preserve ordering where a job depends on the output of another job, such as staleness before proactive rebase filing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Epic maintenance does not run inline before normal task dispatch.
- [ ] #2 Epic completion PRs, stale-epic alerts, proactive rebase filing, and orphan reset behavior remain idempotent.
- [ ] #3 Maintenance jobs use per-project or per-epic locks when touching git branches or tracker state.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:51
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 20:00
---
UNDERSTANDING: My role is Test Engineer for TASK-466.3. The task moves epic maintenance jobs (auto-close epics, epic→main PR, staleness checks, proactive rebase filing, stale rebase pruning, orphan resets, watchdog) out of _handle_dispatch_needed (dispatch lane) and into a new _handle_epic_maintenance() method called from _tick as a maintenance step. This unblocks dispatch from epic I/O latency. I will: (1) Implement _handle_epic_maintenance() with correct job ordering (staleness before rebase filing), (2) Remove these jobs from _handle_dispatch_needed, (3) Add per-project locks for AC#3, (4) Write tests in tests/test_epic_maintenance_lane.py covering lane isolation, ordering, idempotency, and lock behavior.
---

author: oompah
created: 2026-06-08 20:03
---
DISCOVERY: The orchestrator already has MaintenanceJobState, _run_maintenance_job, and _maintenance_jobs infrastructure (from TASK-466.4's scaffold). _handle_dispatch_needed currently runs epic maintenance jobs inline (steps: _auto_close_completed_epics, _open_epic_main_prs, _check_epic_staleness, _dispatch_proactive_rebase_agents, _prune_stale_epic_rebase_states, _reset_orphaned_in_progress). _tick already has steps 5a (watchdog) and 5b (heal_repos) in the maintenance lane pattern. Need to: add _handle_epic_maintenance() coroutine, remove these 6 operations from _handle_dispatch_needed, add step 5c to _tick, and add _epic_maintenance_project_locks dict for per-project locks (AC#3).
---
<!-- COMMENTS:END -->
