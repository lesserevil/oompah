---
id: TASK-467.4
title: Add end-to-end long-tick regression tests and operator diagnostics
status: In Progress
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-08 20:17'
labels:
  - task
  - tick-latency
  - dispatch-performance
  - 'needs:test'
  - 'needs:docs'
dependencies:
  - TASK-465.3
  - TASK-466.4
  - TASK-467.3
references:
  - oompah/orchestrator.py
  - docs
modified_files:
  - tests/test_orchestrator_handlers.py
  - tests/test_project_pause.py
  - docs
parent_task_id: TASK-467
ordinal: 14
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add tests and documented diagnostics for the long-tick scenario that triggered this work: slow cleanup and maintenance should not prevent a separate eligible Open task from dispatching. Include synthetic slow jobs, multiple projects, dependency-blocked tasks, and one ready task in another workstream.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Regression test reproduces one running agent plus one eligible unrelated Open task while maintenance is slow.
- [ ] #2 Expected behavior dispatches the eligible task without waiting for maintenance completion.
- [ ] #3 Operator-facing diagnostics explain which lane or project is currently slow.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 20:14
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 20:17
---
Understanding: This task requires (1) end-to-end regression tests for the long-tick scenario where slow maintenance/cleanup should not block dispatch of eligible Open tasks, and (2) operator-facing diagnostics documentation.

Key findings from code exploration:
-  runs: reconcile → review_check → dispatch_needed → yolo_review → watchdog → heal_repos, in that order
- Dispatch () runs BEFORE maintenance (, ) — this is the key architectural contract to test
- All work runs via  (ThreadPoolExecutor with 8 workers)
- For multi-project dispatch: each project's tracker is fetched in parallel via 

Test plan:
1.  — tests that:
   (a) dispatch completes before maintenance (tick phase ordering contract)
   (b) slow cleanup/yolo does not delay an eligible Open task in a separate project
   (c) multiple projects with dependency-blocked tasks and one ready task: only the ready task dispatches
   (d) synthetic slow maintenance jobs do not exhaust the thread pool from the dispatch path

2.  — operator guide explaining how to read slow-tick logs, use state snapshots, and identify which lane is slow
---
<!-- COMMENTS:END -->
