---
id: TASK-467.4
title: Add end-to-end long-tick regression tests and operator diagnostics
status: In Progress
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-09 05:36'
labels:
  - task
  - tick-latency
  - dispatch-performance
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
created: 2026-06-08 20:14
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-09 05:07
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 05:07
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-09 05:26
---
Agent completed successfully in 1131s (1450376 tokens)
---

author: oompah
created: 2026-06-09 05:26
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 13, Tool calls: 12
- Tokens: 1.4M in / 5.4K out [1.5M total]
- Cost: $0.0000
- Exit: normal, Duration: 18m 51s
- Log: TASK-467.4__20260609T050743Z.jsonl
---

author: oompah
created: 2026-06-09 05:26
---
Agent completed without closing this issue (1131s (1450376 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---

author: oompah
created: 2026-06-09 05:28
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 05:28
---
Focus: Integration Tests Session Specialist
---

author: oompah
created: 2026-06-09 05:29
---
Agent failed: RuntimeError: Codex exec exited with code 1: 2026-06-09T05:29:13.092754Z ERROR codex_core_skills::loader: failed to stat skills path /home/shedwards/.codex/.tmp/plugins/plugins/sentry/skills/sentry/LICENSE.txt: No such file or directory (os error 2)
. Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 05:29
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 24s
- Log: TASK-467.4__20260609T052857Z.jsonl
---

author: oompah
created: 2026-06-09 05:31
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-09 05:35
---
Understanding: The task requires (1) end-to-end regression tests verifying slow maintenance does not block dispatch of an eligible task from a different project/workstream, (2) tests covering synthetic slow jobs, multi-project setups, dependency-blocked tasks, and a ready task in a separate workstream, and (3) operator-facing diagnostics showing which project/lane is slow. Plan: Create tests/test_long_tick_regression.py with TestLongTickRegression class, add project_refresh_metrics to get_snapshot() for AC#3, and write docs/tick-latency-diagnostics.md.
---

author: oompah
created: 2026-06-09 05:36
---
Discovery: The long-tick scenario works as follows: (1) tick sequence is reconcile → review_check → dispatch_needed → yolo_review → watchdog → repo_heal, so dispatch always runs before maintenance; (2) slow maintenance (repo_heal via run_in_executor) blocks the NEXT tick from starting; (3) TASK-467.2 fixed this with bounded per-project refresh using _run_bounded_refresh with timeouts; (4) project_refresh_metrics are tracked in _project_refresh_metrics but not yet exposed in get_snapshot(). Implementing: regression tests in new file tests/test_long_tick_regression.py, adding project_refresh_metrics to get_snapshot() orchestrator_metrics, and docs/tick-latency-diagnostics.md for AC#3.
---
<!-- COMMENTS:END -->
