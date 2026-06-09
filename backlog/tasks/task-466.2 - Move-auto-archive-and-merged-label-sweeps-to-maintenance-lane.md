---
id: TASK-466.2
title: Move auto-archive and merged-label sweeps to maintenance lane
status: Open
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-09 00:25'
labels:
  - task
  - tick-latency
  - maintenance
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
created: 2026-06-08 19:50
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-08 20:08
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 95
- Tokens: 140 in / 4.8K out [5.0K total]
- Cost: $0.0000
- Exit: terminated, Duration: 18m 21s
- Log: TASK-466.2__20260608T195117Z.jsonl
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
created: 2026-06-09 00:05
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:08
---
Understanding: TASK-466.2 is NOT a duplicate — it's a unique task in the TASK-466 epic. Previous agent runs implemented the code changes but failed to commit. The uncommitted working tree has substantial changes: (1) _handle_yolo_review now returns only yolo_ms float (removed archive/merged-label work); (2) _auto_archive and _maybe_run_merged_labels moved to step 5b maintenance lane; (3) _run_step5c_epic_maintenance() added as sync fire-and-forget for step 5c; (4) tests updated to match. Plan: verify tests pass, then commit and push.
---

author: oompah
created: 2026-06-09 00:25
---
Discovery: Previous agents implemented the full TASK-466.2 changes (and TASK-466.3 epic maintenance sync wrapper) but never committed. Key code changes found in working tree: (1) _handle_yolo_review() stripped of archive/merged work, returns single float; (2) _auto_archive() delegates to _run_maintenance_job('auto_archive', min_interval=3600s); (3) new _maybe_run_merged_labels()/_do_merged_labels() delegates to _run_maintenance_job('merged_labels', min_interval=60s); (4) _run_step5b_maintenance() extended with both new jobs; (5) _run_step5c_epic_maintenance() sync wrapper replaces async _handle_epic_maintenance(); (6) tests updated for new signatures. All 214+ tests pass.
---
<!-- COMMENTS:END -->
