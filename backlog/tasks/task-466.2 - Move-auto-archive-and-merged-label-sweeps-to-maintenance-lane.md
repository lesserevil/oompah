---
id: TASK-466.2
title: Move auto-archive and merged-label sweeps to maintenance lane
status: Done
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-09 00:59'
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
created: 2026-06-09 00:05
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 00:35
---
Agent completed successfully in 1758s (18582 tokens)
---

author: oompah
created: 2026-06-09 00:35
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 119, Tool calls: 81
- Tokens: 71 in / 18.5K out [18.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 29m 18s
- Log: TASK-466.2__20260609T000658Z.jsonl
---

author: oompah
created: 2026-06-09 00:35
---
Agent completed without closing this issue (1758s (18582 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---

author: oompah
created: 2026-06-09 00:39
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 00:59
---
Completion: Implementation was fully done in commit 9e842e4 by the previous agent. This run committed the backlog status (Done) and archived task files that were left uncommitted. Branch epic-TASK-466 is now up to date with origin. Key changes delivered: (1) _handle_yolo_review() returns only yolo_ms float; (2) _auto_archive() runs via maintenance gate (3600s interval); (3) new _maybe_run_merged_labels()/_do_merged_labels() via maintenance gate (60s interval) covering _label_merged_issues, _label_merged_epics, _reconcile_stale_in_review_tasks; (4) _run_step5b_maintenance() extended with both jobs; all fire-and-forget off dispatch path. Tests pass.
---
<!-- COMMENTS:END -->
