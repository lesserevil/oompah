---
id: TASK-466.3
title: Move epic rollup staleness and orphan sweeps to maintenance lane
status: Open
assignee: []
created_date: '2026-06-08 18:48'
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
priority: 0
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
