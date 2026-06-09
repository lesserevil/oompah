---
id: TASK-469.5.1
title: Split Oompah into physical API, scheduler, and maintenance services if metrics
  still show coupling
status: Needs CI Fix
assignee: []
created_date: 2026-06-08 23:02
updated_date: 2026-06-09 02:34
labels:
- ci-fix
dependencies: []
parent_task_id: TASK-469.5
ordinal: 175000
priority: 0
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-469.5. TASK-469 delivered the immediate responsiveness isolation with nonblocking issue snapshots, dedicated API execution, dispatch coalescing, bounded candidate scans, and incremental maintenance. If the new orchestrator_metrics/api_metrics still show API stalls caused by scheduler, tracker parsing, or maintenance work after deployment, design and implement a durable local service boundary: oompah-api serving cached state/issues and accepting commands, oompah-scheduler owning dispatch/reconcile/review ticks, and oompah-maintenance owning archive/worktree cleanup/repo heal. Coordinate through SQLite or another local durable queue/cache before considering Redis.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 00:05
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:05
---
Focus: Queue Api Oompah Specialist
---

author: oompah
created: 2026-06-09 01:00
---
Agent completed successfully in 3297s (49223 tokens)
---

author: oompah
created: 2026-06-09 01:00
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 219, Tool calls: 145
- Tokens: 130 in / 49.1K out [49.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 54m 57s
- Log: TASK-469.5.1__20260609T000525Z.jsonl
---

author: oompah
created: 2026-06-09 01:09
---
YOLO: CI tests failed on MR #240. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---

author: oompah
created: 2026-06-09 01:14
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 01:14
---
Focus: CI Failure Fixer
---

author: oompah
created: 2026-06-09 01:14
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 01:14
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 23s
- Log: TASK-469.5.1__20260609T011430Z.jsonl
---

author: oompah
created: 2026-06-09 01:16
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 01:16
---
Focus: Refactoring Specialist
---

author: oompah
created: 2026-06-09 01:19
---
Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 01:19
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 40s
- Log: TASK-469.5.1__20260609T011645Z.jsonl
---

author: oompah
created: 2026-06-09 01:19
---
Retrying (attempt #2, agent: standard)
---

author: oompah
created: 2026-06-09 01:20
---
Focus: CI Failure Fixer
---

author: oompah
created: 2026-06-09 01:20
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-09 01:20
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 36s
- Log: TASK-469.5.1__20260609T012019Z.jsonl
---

author: oompah
created: 2026-06-09 01:21
---
Retrying (attempt #3, agent: standard)
---

author: oompah
created: 2026-06-09 01:21
---
Focus: Refactoring Specialist
---

author: oompah
created: 2026-06-09 01:22
---
Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 80s (attempt #4)
---

author: oompah
created: 2026-06-09 01:22
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 33s
- Log: TASK-469.5.1__20260609T012145Z.jsonl
---

author: oompah
created: 2026-06-09 01:27
---
Retrying (attempt #4, agent: standard)
---

author: oompah
created: 2026-06-09 01:40
---
Understanding: CI test test_process_ipc_commands_pause was failing with 'AssertionError: assert failed == processed'. Root cause: Orchestrator.pause() calls asyncio.ensure_future(self._terminate_all_running()) which requires a running event loop. In Python 3.11, this raises RuntimeError when called from synchronous test context. The exception propagated to _process_ipc_commands which acked the command as 'failed'. Fix: replace asyncio.ensure_future() with asyncio.get_running_loop().create_task() wrapped in try/except RuntimeError. This silently skips agent termination when there's no event loop (safe since tests have no running agents), and works correctly in production where there's always an event loop.
---
<!-- COMMENTS:END -->
