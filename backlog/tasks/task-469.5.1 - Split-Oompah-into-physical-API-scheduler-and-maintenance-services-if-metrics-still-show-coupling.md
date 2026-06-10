---
id: TASK-469.5.1
title: >-
  Split Oompah into physical API, scheduler, and maintenance services if metrics
  still show coupling
status: In Progress
assignee: []
created_date: '2026-06-08 23:02'
updated_date: '2026-06-10 00:08'
labels:
  - ci-fix
dependencies: []
parent_task_id: TASK-469.5
ordinal: 175000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-469.5. TASK-469 delivered the immediate responsiveness isolation with nonblocking issue snapshots, dedicated API execution, dispatch coalescing, bounded candidate scans, and incremental maintenance. If the new orchestrator_metrics/api_metrics still show API stalls caused by scheduler, tracker parsing, or maintenance work after deployment, design and implement a durable local service boundary: oompah-api serving cached state/issues and accepting commands, oompah-scheduler owning dispatch/reconcile/review ticks, and oompah-maintenance owning archive/worktree cleanup/repo heal. Coordinate through SQLite or another local durable queue/cache before considering Redis.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 19:44
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 19:44
---
Focus: CI Failure Fixer
---

author: oompah
created: 2026-06-09 19:45
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=— -> Claude/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 41s
---

author: oompah
created: 2026-06-10 00:04
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-10 00:08
---
Understanding: This task has the ci-fix label, indicating it's tracking CI test failures on branch TASK-469.5.1. The branch was already fixed by a previous agent: commit dc27dac ('Fix pause() to not require event loop in sync context') addressed the root cause. CI run 27178409641 shows SUCCESS across Python 3.11, 3.12, and 3.13. My job is to verify CI passes and close the task properly.
---

author: oompah
created: 2026-06-10 00:08
---
Discovery: CI failure (run 27177010998) was test_ipc.py::test_process_ipc_commands_pause asserting 'failed' == 'processed'. Root cause: Orchestrator.pause() called asyncio.ensure_future() which requires a running event loop. In sync test context (Python 3.11), this raised RuntimeError, causing _process_ipc_commands to ack the command as 'failed'. The fix (commit dc27dac) replaced asyncio.ensure_future() with a try/except RuntimeError pattern. CI run 27178409641 confirms all 3 Python version jobs now pass.
---
<!-- COMMENTS:END -->
