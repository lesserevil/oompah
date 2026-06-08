---
id: TASK-467.1
title: Add per-project locks for tracker writes and git mutations
status: In Progress
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-08 21:08'
labels:
  - task
  - tick-latency
  - dispatch-performance
dependencies:
  - TASK-465.2
references:
  - oompah/orchestrator.py
  - oompah/projects.py
modified_files:
  - oompah/orchestrator.py
  - oompah/projects.py
  - tests/test_submit_queue_concurrency.py
parent_task_id: TASK-467
ordinal: 11
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Introduce explicit per-project and, where needed, per-epic locks for operations that mutate Backlog task files, GitHub tracker state, git worktrees, branches, or review metadata. Use the locks from dispatch, maintenance, YOLO, epic rollup, self-heal, and worker-exit paths so background parallelism cannot corrupt shared state.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Tracker writes for the same project are serialized through a single lock.
- [ ] #2 Git worktree and branch mutations for the same project cannot overlap unsafely.
- [ ] #3 Tests cover concurrent maintenance plus dispatch attempts on the same project.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:51
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 19:52
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-08 20:50
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:51
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-08 21:00
---
Agent stalled 1 time(s) (606s (1495784 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-08 21:01
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 13
- Tokens: 1.5M in / 1.1K out [1.5M total]
- Cost: $0.0000
- Exit: stalled, Duration: 10m 6s
- Log: TASK-467.1__20260608T205214Z.jsonl
---

author: oompah
created: 2026-06-08 21:01
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 21:01
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 21:02
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-08 21:02
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 44s
- Log: TASK-467.1__20260608T210212Z.jsonl
---

author: oompah
created: 2026-06-08 21:03
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-08 21:08
---
Duplicate investigation complete: no duplicate found. TASK-467.1 is unique — no other task implements per-project write locks in ProjectStore or wires them into orchestrator maintenance paths. Prior agent run (commit e213dcf) already implemented the full solution: threading.RLock per project in ProjectStore.project_write_lock(), wrapped create/remove worktree methods, orchestrator _reset_orphaned_in_progress locked tracker writes. All 26 new tests in tests/test_project_locks.py pass. Proceeding to push and close.
---
<!-- COMMENTS:END -->
