---
id: TASK-465.4
title: Wake dispatch loop when graceful restart finishes draining
status: In Progress
assignee: []
created_date: 2026-06-08 19:51
updated_date: 2026-06-09 03:11
labels:
- bug
dependencies: []
parent_task_id: TASK-465
priority: high
ordinal: 165000
oompah.task_costs:
  total_input_tokens: 5760707
  total_output_tokens: 38528
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 5760707
      output_tokens: 38528
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 4529271
    output_tokens: 9031
    cost_usd: 0.0
    recorded_at: '2026-06-08T21:21:36.254308+00:00'
  - profile: default
    model: unknown
    input_tokens: 36
    output_tokens: 10475
    cost_usd: 0.0
    recorded_at: '2026-06-08T22:15:49.817245+00:00'
  - profile: default
    model: unknown
    input_tokens: 1231376
    output_tokens: 14613
    cost_usd: 0.0
    recorded_at: '2026-06-09T00:45:10.375990+00:00'
  - profile: deep
    model: unknown
    input_tokens: 24
    output_tokens: 4409
    cost_usd: 0.0
    recorded_at: '2026-06-09T01:16:46.063439+00:00'
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
created: 2026-06-08 19:51
---
Filed from live recovery: graceful restart saved restart_issues but left the event-driven loop blocked on the dispatch queue.
---
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-08 20:45

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-08 20:45

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-08 20:46

Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-08 20:46

Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 13s
- Log: TASK-465.4__20260608T204537Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-08 20:48

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-08 20:49

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-08 20:50

Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-08 20:50

Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 26s
- Log: TASK-465.4__20260608T204940Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9
author: oompah
created: 2026-06-08 20:52

Retrying (attempt #2, agent: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 10
author: oompah
created: 2026-06-08 20:54

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 11
author: oompah
created: 2026-06-08 21:21

Agent completed successfully in 1728s (4538302 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 12
author: oompah
created: 2026-06-08 21:22

Run #3 [attempt=3, profile=deep, role=deep -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 30, Tool calls: 29
- Tokens: 4.5M in / 9.0K out [4.5M total]
- Cost: $0.0000
- Exit: normal, Duration: 28m 48s
- Log: TASK-465.4__20260608T205437Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 13
author: oompah
created: 2026-06-08 22:06

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 14
author: oompah
created: 2026-06-08 22:06

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 15
author: oompah
created: 2026-06-08 22:15

Agent completed successfully in 562s (10511 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 16
author: oompah
created: 2026-06-08 22:16

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 67, Tool calls: 40
- Tokens: 36 in / 10.5K out [10.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 22s
- Log: TASK-465.4__20260608T220652Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 17
author: oompah
created: 2026-06-09 00:00

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 18
author: oompah
created: 2026-06-09 00:00

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 19
author: oompah
created: 2026-06-09 00:24

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 20
author: oompah
created: 2026-06-09 00:24

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 21
author: oompah
created: 2026-06-09 00:45

Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 22
author: oompah
created: 2026-06-09 00:45

Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 14, Tool calls: 13
- Tokens: 1.2M in / 14.6K out [1.2M total]
- Cost: $0.0000
- Exit: error, Duration: 20m 35s
- Log: TASK-465.4__20260609T002534Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 23
author: oompah
created: 2026-06-09 00:48

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 24
author: oompah
created: 2026-06-09 00:49

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 25
author: oompah
created: 2026-06-09 00:54

Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 26
author: oompah
created: 2026-06-09 00:55

Run #2 [attempt=2, profile=deep, role=deep -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 6m 3s
- Log: TASK-465.4__20260609T004953Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 27
author: oompah
created: 2026-06-09 00:56

Retrying (attempt #2, agent: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 28
author: oompah
created: 2026-06-09 00:56

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 29
author: oompah
created: 2026-06-09 01:16

Agent completed successfully in 1217s (4433 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 30
author: oompah
created: 2026-06-09 01:17

Run #3 [attempt=3, profile=deep, role=deep -> Claude/default]
- Turns: 43, Tool calls: 28
- Tokens: 24 in / 4.4K out [4.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 20m 17s
- Log: TASK-465.4__20260609T005734Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 31
author: oompah
created: 2026-06-09 03:06

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 32
author: oompah
created: 2026-06-09 03:06

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 33
author: oompah
created: 2026-06-09 03:07

Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 34
author: oompah
created: 2026-06-09 03:07

Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 26s
- Log: TASK-465.4__20260609T030651Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 35
author: oompah
created: 2026-06-09 03:08

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 36
author: oompah
created: 2026-06-09 03:08

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 37
author: oompah
created: 2026-06-09 03:09

Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 38
author: oompah
created: 2026-06-09 03:09

Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 37s
- Log: TASK-465.4__20260609T030910Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 39
author: oompah
created: 2026-06-09 03:11

Retrying (attempt #2, agent: deep)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
