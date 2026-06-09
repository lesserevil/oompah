---
id: TASK-466.2
title: Move auto-archive and merged-label sweeps to maintenance lane
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
  - TASK-466.1
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_merged.py
parent_task_id: TASK-466
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

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:50
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 19:57
---
UNDERSTANDING: Task requires writing tests for moving auto-archive, merged-issue labeling, merged epic labeling, and stale In Review reconciliation out of the dispatch-critical tick path (_handle_yolo_review) into a maintenance lane with its own cadence.

Current state: These sweeps are called inline from _handle_yolo_review() which runs every dispatch tick. The _auto_archive already has a 1-hour throttle, but the merged-label/in-review sweeps run every tick.

Plan:
1. Write tests for the new maintenance cadence behavior: merged-label and in-review sweeps should have their own throttle (like _auto_archive does with _AUTO_ARCHIVE_INTERVAL_S)
2. Write tests that verify the sweeps do NOT block candidate dispatch
3. Write tests for idempotency and error handling (logged once, not every tick)
4. Write tests that verify correct transitions still happen after maintenance job runs
5. Target tests/test_orchestrator_merged.py (as specified in Modified files)
---

author: oompah
created: 2026-06-08 19:58
---
DISCOVERY: Key findings:

1. _auto_archive() already has _AUTO_ARCHIVE_INTERVAL_S=3600 throttle INSIDE the method itself
2. _label_merged_issues(), _label_merged_epics(), _reconcile_stale_in_review_tasks() have NO throttle - they run every tick via _handle_yolo_review()
3. The maintenance lane pattern (_maybe_heal_repos, _maybe_run_watchdog) uses a monotonic timer check that guards the actual work
4. The task needs: _maybe_run_merged_label_sweep() wrapping all 3 merged/reconcile methods with a new throttle interval
5. _handle_yolo_review() should eventually stop calling these sweeps directly (maintenance lane move)
6. Test file: tests/test_orchestrator_merged.py needs new test classes for the throttled sweep behavior and maintenance lane isolation
---
<!-- COMMENTS:END -->
