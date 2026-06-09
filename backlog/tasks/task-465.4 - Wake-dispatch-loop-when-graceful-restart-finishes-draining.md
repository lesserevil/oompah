---
id: TASK-465.4
title: Wake dispatch loop when graceful restart finishes draining
status: Done
assignee: []
created_date: '2026-06-08 19:51'
updated_date: '2026-06-09 03:16'
labels:
  - bug
dependencies: []
parent_task_id: TASK-465
priority: high
ordinal: 165000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During live recovery on 2026-06-08, POST /api/v1/orchestrator/restart saved undrained restart_issues and set _stopping=True, but the main event-driven dispatch loop was blocked on _dispatch_queue.get() and did not wake to exit/re-exec. The old process kept serving port 8090 until manually killed.

Fix graceful_restart so it wakes the run loop after setting _stopping, or otherwise cancels/interrupts the queue wait deterministically. Add a regression test that starts the event-driven loop, invokes graceful_restart with an undrained running task, and proves _run returns wants_restart=True without requiring another external event.

Acceptance criteria:
- Graceful restart exits/re-execs after the drain timeout even when the dispatch queue is idle.
- Undrained tasks are persisted for restart recovery exactly once.
- Tests cover the idle-queue drain-complete case.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 20:45
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:45
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 20:46
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-08 20:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 13s
- Log: TASK-465.4__20260608T204537Z.jsonl
---

author: oompah
created: 2026-06-08 20:48
---
Agent dispatched (profile: deep)
---

author: oompah
created: 2026-06-08 20:49
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 20:50
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-08 20:50
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 26s
- Log: TASK-465.4__20260608T204940Z.jsonl
---

author: oompah
created: 2026-06-08 20:52
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-08 20:54
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-08 21:21
---
Agent completed successfully in 1728s (4538302 tokens)
---

author: oompah
created: 2026-06-08 21:22
---
Run #3 [attempt=3, profile=deep, role=deep -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 30, Tool calls: 29
- Tokens: 4.5M in / 9.0K out [4.5M total]
- Cost: $0.0000
- Exit: normal, Duration: 28m 48s
- Log: TASK-465.4__20260608T205437Z.jsonl
---

author: oompah
created: 2026-06-08 22:06
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 22:06
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 22:15
---
Agent completed successfully in 562s (10511 tokens)
---

author: oompah
created: 2026-06-08 22:16
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 67, Tool calls: 40
- Tokens: 36 in / 10.5K out [10.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 22s
- Log: TASK-465.4__20260608T220652Z.jsonl
---

author: oompah
created: 2026-06-09 00:00
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:00
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 00:24
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:24
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-09 00:45
---
Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 00:45
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 14, Tool calls: 13
- Tokens: 1.2M in / 14.6K out [1.2M total]
- Cost: $0.0000
- Exit: error, Duration: 20m 35s
- Log: TASK-465.4__20260609T002534Z.jsonl
---

author: oompah
created: 2026-06-09 00:48
---
Agent dispatched (profile: deep)
---

author: oompah
created: 2026-06-09 00:49
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-09 00:54
---
Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 00:55
---
Run #2 [attempt=2, profile=deep, role=deep -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 6m 3s
- Log: TASK-465.4__20260609T004953Z.jsonl
---

author: oompah
created: 2026-06-09 00:56
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-09 00:56
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:16
---
Agent completed successfully in 1217s (4433 tokens)
---

author: oompah
created: 2026-06-09 01:17
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/default]
- Turns: 43, Tool calls: 28
- Tokens: 24 in / 4.4K out [4.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 20m 17s
- Log: TASK-465.4__20260609T005734Z.jsonl
---

author: oompah
created: 2026-06-09 03:06
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 03:06
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 03:07
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 03:07
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 26s
- Log: TASK-465.4__20260609T030651Z.jsonl
---

author: oompah
created: 2026-06-09 03:08
---
Agent dispatched (profile: deep)
---

author: oompah
created: 2026-06-09 03:08
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 03:09
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 03:09
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 37s
- Log: TASK-465.4__20260609T030910Z.jsonl
---

author: oompah
created: 2026-06-09 03:11
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-09 03:12
---
Focus: Event Queue Pipeline Specialist
---

author: oompah
created: 2026-06-09 03:14
---
Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-09 03:14
---
Run #3 [attempt=3, profile=deep, role=deep -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 2m 7s
- Log: TASK-465.4__20260609T031312Z.jsonl
---

author: oompah
created: 2026-06-09 03:14
---
Retrying (attempt #3, agent: deep)
---

author: oompah
created: 2026-06-09 03:16
---
Continuation run: verified implementation is complete and all 4 TestGracefulRestartShutdownEvent tests pass. Task was already done in commit 407b2e8 but the status was inadvertently left as In Progress by a subsequent agent. Closing now.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed graceful_restart() to wake the idle dispatch loop: added DispatchEventType.SHUTDOWN enum value (oompah/orchestrator.py), graceful_restart() posts a SHUTDOWN event after setting _stopping=True to unblock queue.get() waits. Added dedup merge logic so undrained tasks are persisted exactly once across repeated calls. Added TestGracefulRestartShutdownEvent with 4 regression tests covering: SHUTDOWN event type, event posting, idle-queue drain-complete wakeup, and single-persist invariant. All 4 tests pass. Implemented in commit 407b2e8 on epic-TASK-465.
<!-- SECTION:FINAL_SUMMARY:END -->
