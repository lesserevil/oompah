---
id: TASK-466.2
title: Move auto-archive and merged-label sweeps to maintenance lane
status: Open
assignee: []
created_date: '2026-06-08 18:48'
labels:
  - task
  - tick-latency
  - maintenance
  - 'needs:backend'
  - 'needs:test'
dependencies:
  - TASK-466.1
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_merged.py
parent_task_id: TASK-466
priority: 0
ordinal: 7
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move auto-archive, merged issue labeling, merged epic labeling, and stale In Review reconciliation out of the dispatch-critical tick path. Keep forge-state reuse where helpful, but allow the sweeps to run on their own cadence with bounded runtime and idempotent retries.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Archive and merged-label sweeps run on a maintenance cadence and do not block candidate dispatch.
- [ ] #2 Closed merged tasks still transition to Merged/Archived correctly after the maintenance job runs.
- [ ] #3 Failures are logged once per fingerprint or surfaced in diagnostics without spamming every tick.
<!-- AC:END -->
