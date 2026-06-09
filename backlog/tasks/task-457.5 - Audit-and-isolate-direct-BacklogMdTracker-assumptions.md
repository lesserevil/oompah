---
id: TASK-457.5
title: Audit and isolate direct BacklogMdTracker assumptions
status: Open
assignee: []
created_date: '2026-06-08 17:56'
updated_date: '2026-06-09 03:24'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-457.3
  - TASK-457.4
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/orchestrator.py
  - oompah/server.py
  - oompah/error_watcher.py
parent_task_id: TASK-457
priority: high
ordinal: 113000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Find every direct BacklogMdTracker type check, constructor call, task-file path assumption, worker-workspace status read, and Backlog-specific comment in server/orchestrator/watchers. Convert generic call sites to the tracker protocol and document explicitly legacy-only paths.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Generic flows no longer assume tasks are files in a managed checkout.
- [ ] #2 Legacy Backlog-only paths are named and guarded.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 23:59
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:00
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 00:15
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:15
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 00:30
---
Agent stalled 1 time(s) (908s (801302 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-09 00:30
---
Run #1 [attempt=1, profile=default, role=fast -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 11, Tool calls: 11
- Tokens: 800.6K in / 673 out [801.3K total]
- Cost: $0.0000
- Exit: stalled, Duration: 15m 8s
- Log: TASK-457.5__20260609T001551Z.jsonl
---

author: oompah
created: 2026-06-09 00:31
---
Agent dispatched (profile: standard)
---

author: oompah
created: 2026-06-09 00:32
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:32
---
Agent stalled 2 time(s) (3658s (6878 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-09 01:32
---
Run #2 [attempt=2, profile=standard, role=standard -> Claude/default]
- Turns: 182, Tool calls: 121
- Tokens: 188 in / 6.7K out [6.9K total]
- Cost: $0.0000
- Exit: stalled, Duration: 1h 0m 58s
- Log: TASK-457.5__20260609T003236Z.jsonl
---

author: oompah
created: 2026-06-09 01:36
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-09 01:36
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:38
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 40s (attempt #3)
---

author: oompah
created: 2026-06-09 01:38
---
Run #3 [attempt=3, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 40s
- Log: TASK-457.5__20260609T013726Z.jsonl
---

author: oompah
created: 2026-06-09 01:39
---
Retrying (attempt #3, agent: standard)
---

author: oompah
created: 2026-06-09 01:39
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:39
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 80s (attempt #4)
---

author: oompah
created: 2026-06-09 01:39
---
Run #4 [attempt=4, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 18s
- Log: TASK-457.5__20260609T013937Z.jsonl
---

author: oompah
created: 2026-06-09 01:41
---
Retrying (attempt #4, agent: standard)
---

author: oompah
created: 2026-06-09 01:41
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:42
---
Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 160s (attempt #5)
---

author: oompah
created: 2026-06-09 01:42
---
Run #5 [attempt=5, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 51s
- Log: TASK-457.5__20260609T014206Z.jsonl
---

author: oompah
created: 2026-06-09 01:45
---
Retrying (attempt #5, agent: standard)
---

author: oompah
created: 2026-06-09 01:45
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:45
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 300s (attempt #6)
---

author: oompah
created: 2026-06-09 01:45
---
Run #6 [attempt=6, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 20s
- Log: TASK-457.5__20260609T014544Z.jsonl
---

author: oompah
created: 2026-06-09 01:51
---
Retrying (attempt #6, agent: standard)
---

author: oompah
created: 2026-06-09 01:51
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 01:51
---
Agent failed: HTTP 500 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.InternalServerError: InternalServerError: OpenAIException - Cannot connect to host nemotron-ultra-rl-052726-vllm-dynamo.prd.astra.nvidia.com:443 ssl:True [SSLCertVerificationError: (1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)')]. Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"500"}}. Retrying in 300s (attempt #7)
---

author: oompah
created: 2026-06-09 01:52
---
Run #7 [attempt=7, profile=standard, role=standard -> InferenceAPI/nvidia/nvidia/nemotron-3-ultra]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 41s
- Log: TASK-457.5__20260609T015126Z.jsonl
---

author: oompah
created: 2026-06-09 01:58
---
Retrying (attempt #7, agent: standard)
---

author: oompah
created: 2026-06-09 02:07
---
Understanding: TASK-457.5 is not a duplicate — it is the last piece of the TASK-457 tracker-abstraction series, which adds isinstance(tracker, BacklogMdTracker) guards in server/orchestrator/watchers so that API-backed trackers (e.g. GitHub Issues) skip Backlog.md-specific file operations. All prerequisite tasks (457.1–457.4) are Done. Previous agent runs made code changes but didn't commit them.
---

author: oompah
created: 2026-06-09 02:08
---
Discovery: Found 6 call sites in orchestrator.py with direct BacklogMdTracker assumptions (all without guards): _shared_epic_child_done, _blocker_satisfied, _shared_epic_child_terminal, _epic_child_effective_state, _sync_issue_task_file_to_workspace, _fetch_terminal_issue_from_worker_workspace. Minor Backlog-specific wording in server.py and error_watcher.py. Previous agent added all the isinstance guards but did not commit.
---
<!-- COMMENTS:END -->
