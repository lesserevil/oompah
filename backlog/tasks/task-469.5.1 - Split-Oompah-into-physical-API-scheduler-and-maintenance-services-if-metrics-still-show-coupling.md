---
id: TASK-469.5.1
title: >-
  Split Oompah into physical API, scheduler, and maintenance services if metrics
  still show coupling
status: Done
assignee: []
created_date: '2026-06-08 23:02'
updated_date: '2026-06-10 06:16'
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
created: 2026-06-10 05:50
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-10 05:55
---
Understanding: This task is labeled ci-fix, so my role is to identify and fix CI test failures. Current branch is epic-TASK-469.5. The /tmp filesystem was out of inodes preventing local test execution - cleaned up old pytest dirs. Now running tests to identify actual failures.
---

author: oompah
created: 2026-06-10 06:14
---
Discovery: PR #240 (TASK-469.5.1) was already merged to main. The initial CI failure (run 27177010998) was fixed by a subsequent commit (run 27178409641 passed). After the merge, commit 3fd1427 (TASK-466 epic) reset the task status to 'Needs CI Fix' in backlog, causing re-dispatch. Current CI on main is passing for all Python versions. All 59 tests in test_ipc.py and test_state_api_responsiveness.py pass locally.
---

author: oompah
created: 2026-06-10 06:14
---
Verification: 59/59 tests pass locally for test_ipc.py and test_state_api_responsiveness.py. GitHub CI run 27178409641 shows all 3 Python version jobs (3.11, 3.12, 3.13) passing. Main branch CI is green. No code changes needed - the fix was already merged.
---

author: oompah
created: 2026-06-10 06:16
---
Completion: CI fix was complete before PR #240 merged to main. The re-dispatch was caused by TASK-466's merge resetting the task status. All 59 IPC/responsiveness tests pass locally; GitHub CI is green. No further action needed - marking Done.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
CI was already fixed before PR #240 merged. TASK-466 commit 3fd1427 reset status to 'Needs CI Fix' causing re-dispatch. Verified: all 59 IPC and state-responsiveness tests pass; main CI green on 3.11/3.12/3.13. SQLite-backed IPC service boundary shipped in PR #240 as designed.
<!-- SECTION:FINAL_SUMMARY:END -->
