---
id: TASK-466.3
title: Move epic rollup staleness and orphan sweeps to maintenance lane
status: Open
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-09 01:44'
labels:
  - task
  - tick-latency
  - maintenance
  - epic
dependencies:
  - TASK-466.1
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_epic_strategy.py
  - tests/test_epic_rebase_state.py
parent_task_id: TASK-466
ordinal: 8
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move auto-close completed epics, epic-to-main PR opening, epic staleness checks, proactive rebase filing, stale epic rebase pruning, watchdog scans, and orphaned In Progress resets into bounded maintenance jobs. Preserve ordering where a job depends on the output of another job, such as staleness before proactive rebase filing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Epic maintenance does not run inline before normal task dispatch.
- [ ] #2 Epic completion PRs, stale-epic alerts, proactive rebase filing, and orphan reset behavior remain idempotent.
- [ ] #3 Maintenance jobs use per-project or per-epic locks when touching git branches or tracker state.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:51
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-08 19:51
---
Focus: Test Engineer
---

author: oompah
created: 2026-06-08 20:08
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 95
- Tokens: 153 in / 5.1K out [5.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 54s
- Log: TASK-466.3__20260608T195152Z.jsonl
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
created: 2026-06-09 00:07
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:07
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:12
---
Agent stalled 1 time(s) (3911s (7575 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 01:12
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 193, Tool calls: 127
- Tokens: 199 in / 7.4K out [7.6K total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 5m 11s
- Log: TASK-466.3__20260609T000725Z.jsonl
---

author: oompah
created: 2026-06-09 01:14
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 01:14
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:14
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 01:14
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 18s
- Log: TASK-466.3__20260609T011411Z.jsonl
---

author: oompah
created: 2026-06-09 01:16
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-09 01:17
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:18
---
Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-09 01:19
---
Run #3 [attempt=3, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 37s
- Log: TASK-466.3__20260609T011719Z.jsonl
---

author: oompah
created: 2026-06-09 01:20
---
Retrying (attempt #3, agent: standard)
---

author: oompah
created: 2026-06-09 01:20
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:20
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 80s (attempt #4)
---

author: oompah
created: 2026-06-09 01:20
---
Run #4 [attempt=4, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 22s
- Log: TASK-466.3__20260609T012032Z.jsonl
---

author: oompah
created: 2026-06-09 01:22
---
Retrying (attempt #4, agent: standard)
---

author: oompah
created: 2026-06-09 01:44
---
Understanding: This task requires moving epic rollup maintenance (auto-close, epic PR opening, staleness checks, proactive rebase filing, stale rebase pruning, watchdog scans, orphaned In Progress resets) from the inline dispatch tick path to bounded maintenance jobs. As Duplicate Investigator, I confirmed this is NOT a duplicate of any other task - it is a distinct sub-task of TASK-466 (the parent epic). The implementation has already been completed as part of TASK-466.2 work and is on origin/epic-TASK-466. Proceeding to verify and close.
---

author: oompah
created: 2026-06-09 01:44
---
Discovery: The implementation was completed in TASK-466.2 commits (9e842e4, a2d6e5f). Key findings: (1) _run_step5c_epic_maintenance() was added in commit 9e842e4, running all 6 epic maintenance jobs sequentially via _run_maintenance_job() gate; (2) The function runs fire-and-forget from _tick() via _epic_maintenance_future (not awaited), keeping it off the dispatch critical path; (3) Jobs: epic_auto_close (60s), epic_open_prs (60s), epic_staleness (300s), epic_rebase_filing (300s, must follow staleness), epic_prune_rebase (300s), epic_orphan_reset (60s); (4) Per-project lock mechanism (_get_project_maintenance_lock) is defined and tested; (5) 151 related tests pass.
---

author: oompah
created: 2026-06-09 01:44
---
Verification: All acceptance criteria are met. AC#1: _handle_dispatch_needed() contains a comment that epic close/PR/staleness/rebase/orphan-reset have moved to _run_step5c_epic_maintenance (step 5c), not inline. AC#2: All jobs use _run_maintenance_job() with idempotent semantics and in-flight coalescing. AC#3: _get_project_maintenance_lock() provides per-project threading.Lock tested in TestRunStep5cEpicMaintenance (3 tests). 151 tests pass including 13 in TestRunStep5cEpicMaintenance, 23 in test_epic_rebase_state.py, 78 in test_epic_strategy.py, 37 in test_epic_staleness.py + test_epic_auto_close.py.
---
<!-- COMMENTS:END -->
