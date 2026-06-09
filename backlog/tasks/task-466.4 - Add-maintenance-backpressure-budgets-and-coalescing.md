---
id: TASK-466.4
title: Add maintenance backpressure budgets and coalescing
status: Open
assignee: []
created_date: '2026-06-08 18:48'
updated_date: '2026-06-09 03:06'
labels:
  - task
  - tick-latency
  - maintenance
dependencies:
  - TASK-466.2
  - TASK-466.3
references:
  - oompah/orchestrator.py
modified_files:
  - oompah/orchestrator.py
  - tests/test_orchestrator_handlers.py
parent_task_id: TASK-466
ordinal: 9
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add scheduling controls so maintenance jobs cannot starve dispatch: per-job minimum interval, max runtime or item budget, in-flight coalescing, skip counters, and explicit next-run timestamps. The scheduler should drop redundant maintenance requests while one is running and should record when a job is skipped because dispatch is busy.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A long maintenance job cannot launch duplicate copies of itself.
- [ ] #2 Maintenance jobs enforce configured or hard-coded safety budgets and resume on a later run.
- [ ] #3 State snapshots include enough maintenance lane status to diagnose skipped, running, failed, and completed jobs.
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
created: 2026-06-08 20:09
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 106
- Tokens: 164 in / 5.3K out [5.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 38s
- Log: TASK-466.4__20260608T195213Z.jsonl
---

author: oompah
created: 2026-06-09 01:53
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 01:54
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:54
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 01:54
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 36s
- Log: TASK-466.4__20260609T015421Z.jsonl
---

author: oompah
created: 2026-06-09 01:55
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 01:56
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 02:51
---
Agent failed: Exception: Command failed with exit code 143 (exit code: 143)
Error output: Check stderr output for details. Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 02:51
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 242, Tool calls: 149
- Tokens: 248 in / 9.1K out [9.3K total]
- Cost: $0.0000
- Exit: error, Duration: 55m 34s
- Log: TASK-466.4__20260609T015610Z.jsonl
---

author: oompah
created: 2026-06-09 02:52
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-09 02:52
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-09 02:53
---
Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-09 02:53
---
Run #3 [attempt=3, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 52s
- Log: TASK-466.4__20260609T025301Z.jsonl
---

author: oompah
created: 2026-06-09 02:54
---
Retrying (attempt #3, agent: standard)
---

author: oompah
created: 2026-06-09 03:06
---
Understanding: Reviewing prior work. The MaintenanceJobState dataclass and _run_maintenance_job gate are fully implemented with in-flight coalescing, interval throttling, skip counters, max_runtime_s budget, and _job_deadline_exceeded(). The snapshot exposes per-job state. However, there are no dedicated unit tests for the _run_maintenance_job gate itself or _job_deadline_exceeded. Adding TestRunMaintenanceJobGate tests to close the coverage gap for the three acceptance criteria.
---
<!-- COMMENTS:END -->
