---
id: TASK-466.1
title: Move worktree cleanup and repo self-heal to maintenance lane
status: Open
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-08 23:03'
labels:
  - task
  - tick-latency
  - maintenance
dependencies:
  - TASK-465.2
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-466
ordinal: 6
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Run terminal worktree cleanup and managed checkout self-heal as scheduled maintenance jobs instead of inline work in the full dispatch tick. Preserve the rule that only merged and archived worktrees are removed, keep done/conflict worktrees intact, and expose job status in tick diagnostics.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Terminal worktree cleanup no longer contributes to dispatch tick latency.
- [ ] #2 Done worktrees are not deleted unless the task is also merged or archived.
- [ ] #3 Repo self-heal remains automatic and reports failures without blocking dispatch.
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
- Turns: 0, Tool calls: 107
- Tokens: 154 in / 5.2K out [5.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 18m 41s
- Log: TASK-466.1__20260608T195055Z.jsonl
---

author: oompah
created: 2026-06-08 20:49
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:50
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-08 21:08
---
Agent stalled 1 time(s) (1105s (2732224 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-08 21:08
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 20, Tool calls: 20
- Tokens: 2.7M in / 9.3K out [2.7M total]
- Cost: $0.0000
- Exit: stalled, Duration: 18m 25s
- Log: TASK-466.1__20260608T205034Z.jsonl
---

author: oompah
created: 2026-06-08 21:08
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 21:09
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 22:16
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 22:17
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-08 22:54
---
Agent completed successfully in 2264s (4002238 tokens)
---

author: oompah
created: 2026-06-08 22:54
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 31, Tool calls: 30
- Tokens: 4.0M in / 11.8K out [4.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 37m 44s
- Log: TASK-466.1__20260608T221741Z.jsonl
---

author: oompah
created: 2026-06-08 22:54
---
Agent completed without landing — no commits found on origin for branch `epic-TASK-466`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---

author: oompah
created: 2026-06-08 22:57
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 23:03
---
Understanding: This task moves terminal worktree cleanup and repo self-heal from inline dispatch work to a scheduled maintenance lane. Previous agents did the implementation work but didn't commit. As Duplicate Investigator, I checked TASK-469.2 (Budget auto-archive and worktree cleanup) and TASK-452 (Preserve Done worktrees) — neither is a duplicate. TASK-469.2 is broader scope (auto-archive + budget/cursor); TASK-452 is Done. Proceeding to commit the completed implementation.
---
<!-- COMMENTS:END -->
