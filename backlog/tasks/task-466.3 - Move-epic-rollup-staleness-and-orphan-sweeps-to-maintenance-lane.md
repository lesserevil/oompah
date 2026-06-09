---
id: TASK-466.3
title: Move epic rollup staleness and orphan sweeps to maintenance lane
status: Open
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-09 00:18'
labels:
  - task
  - tick-latency
  - maintenance
  - epic
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
created: 2026-06-08 19:51
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-08 20:08
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 95
- Tokens: 153 in / 5.1K out [5.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 54s
- Log: TASK-466.3__20260608T195152Z.jsonl
---

author: oompah
created: 2026-06-08 23:05
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 23:05
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 00:07
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:16
---
Understanding: TASK-466.3 is NOT a duplicate. It's a distinct subtask in the TASK-466 epic about moving epic rollup staleness and orphan sweeps to maintenance lane. Previous agent runs (Test Engineer + two Duplicate Investigators) did not complete. The working tree already contains the core implementation: _run_step5c_epic_maintenance() replaces the old async _handle_epic_maintenance(), six maintenance jobs (epic_auto_close, epic_open_prs, epic_staleness, epic_rebase_filing, epic_prune_rebase, epic_orphan_reset) use _run_maintenance_job() gating, and _epic_maintenance_future provides fire-and-forget coalescing. However, there are no dedicated unit tests for _run_step5c_epic_maintenance itself. Plan: (1) add tests for step 5c covering AC#1/2/3, (2) run full test suite, (3) commit both TASK-466.2 and TASK-466.3 changes, (4) mark done.
---
<!-- COMMENTS:END -->
