---
id: TASK-467.2
title: Bound and parallelize project-scoped refresh work
status: In Progress
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-08 23:08'
labels:
  - task
  - tick-latency
  - dispatch-performance
dependencies:
  - TASK-467.1
  - TASK-465.1
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-467
ordinal: 12
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Refactor candidate fetch, running-state refresh, review fetch, merged-branch fetch, and maintenance project scans to use bounded per-project concurrency with timeouts and stale-cache fallback. The dispatch lane should use the freshest complete data available while avoiding one slow project blocking all other projects.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A slow or wedged project refresh does not block dispatch for unrelated projects after its timeout.
- [ ] #2 Review/open-PR gating remains conservative when refresh data is stale or unavailable.
- [ ] #3 Per-project refresh timings and timeout counts are visible in diagnostics.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 20:12
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 20:12
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-08 20:19
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 59
- Tokens: 88 in / 2.7K out [2.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 6m 50s
- Log: TASK-467.2__20260608T201342Z.jsonl
---

author: oompah
created: 2026-06-08 21:12
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 21:13
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 21:13
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-08 21:13
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 22s
- Log: TASK-467.2__20260608T211307Z.jsonl
---

author: oompah
created: 2026-06-08 21:13
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 21:14
---
Focus: Refactoring Specialist
---

author: oompah
created: 2026-06-08 22:17
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 22:18
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-08 22:28
---
Agent completed successfully in 663s (1652816 tokens)
---

author: oompah
created: 2026-06-08 22:28
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 14, Tool calls: 13
- Tokens: 1.6M in / 6.3K out [1.7M total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 3s
- Log: TASK-467.2__20260608T221812Z.jsonl
---

author: oompah
created: 2026-06-08 22:29
---
Agent completed without closing this issue (663s (1652816 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---

author: oompah
created: 2026-06-08 22:33
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 22:33
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-08 22:43
---
Agent completed successfully in 596s (1634366 tokens)
---

author: oompah
created: 2026-06-08 22:43
---
Run #2 [attempt=2, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 14, Tool calls: 13
- Tokens: 1.6M in / 11.9K out [1.6M total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 56s
- Log: TASK-467.2__20260608T223351Z.jsonl
---

author: oompah
created: 2026-06-08 22:44
---
Agent completed without closing this issue (596s (1634366 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---

author: oompah
created: 2026-06-08 22:46
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-08 22:58
---
Understanding: This is not a duplicate. Previous agents did substantial implementation work but left the task in a broken state: (1) tests/test_orchestrator_handlers.py has 5 failing tests because they mock old sync methods (_fetch_all_reviews, _fetch_all_merged_branches) but the code now calls async bounded versions; (2) config.py has duplicated field definitions; (3) no tests cover the new bounded refresh infrastructure. Fixing these issues now.
---

author: oompah
created: 2026-06-08 23:08
---
Implementation: Fixed 3 issues left by previous agents: (1) Removed duplicate field definitions in config.py; (2) Resolved merge conflict in config.py that was causing SyntaxError by merging dispatch/maintenance config params from upstream with project_refresh_* params from stale stash; (3) Updated 12 tests in test_orchestrator_handlers.py to mock _fetch_all_reviews_bounded and _fetch_all_merged_branches_bounded (AsyncMock) instead of old sync methods. Added 11 new tests in TestBoundedProjectRefresh covering AC#1 (timeout/stale fallback), AC#2 (conservative gating), AC#3 (metrics recording).
---
<!-- COMMENTS:END -->
