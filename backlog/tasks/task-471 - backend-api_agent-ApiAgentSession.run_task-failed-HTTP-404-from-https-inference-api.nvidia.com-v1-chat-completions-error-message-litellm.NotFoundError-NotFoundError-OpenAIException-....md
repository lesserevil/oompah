---
id: TASK-471
title: >-
  [backend:api_agent] ApiAgentSession.run_task failed: HTTP 404 from
  https://inference-api.nvidia.com/v1/chat/completions:
  {"error":{"message":"litellm.NotFoundError: NotFoundError: OpenAIException
  -...
status: Done
assignee: []
created_date: '2026-06-09 00:40'
updated_date: '2026-06-09 19:57'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 177000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 404 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.NotFoundError: NotFoundError: OpenAIException - . Received Model Group=nvidia/nvidia/nemotron-3-ultra\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"404"}}
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-09 19:45
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 19:45
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 19:47
---
Agent completed successfully in 119s (3400 tokens)
---

author: oompah
created: 2026-06-09 19:47
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 29, Tool calls: 17
- Tokens: 17 in / 3.4K out [3.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 59s
- Log: TASK-471__20260609T194549Z.jsonl
---

author: oompah
created: 2026-06-09 19:48
---
Review handoff deferred: the task branch has unmerged work, but this project is at its open review limit.

Branch: `TASK-471`
Target branch: `main`
Unmerged commits: 5 commits
Open reviews: 1/1

oompah will create the review automatically when review capacity is available.

Recent commits:
  1199393 TASK-471: close task as Done
  4bae920 TASK-471: update task comments (completion)
  825b228 TASK-471: update task comments (duplicate investigator run)
  2a4cf47 TASK-471: update task comments
  1da9020 TASK-471: treat litellm HTTP 404 NotFoundError as transient
---

author: oompah
created: 2026-06-09 19:57
---
Duplicate investigation (run #2): confirmed NOT a duplicate. Searched for tasks matching 'nvidia', 'NotFoundError', 'HTTP 404', and 'litellm' — only TASK-471 matches. Prior 400-error tasks (TASK-432, TASK-435, TASK-438, TASK-440, TASK-442, TASK-443) are distinct error types (BadRequestError/ContextWindowExceeded). Task is already Done; fix committed on branch (litellm HTTP 404 NotFoundError now raises TransientServerError, 8 unit tests passing).
---
<!-- COMMENTS:END -->
