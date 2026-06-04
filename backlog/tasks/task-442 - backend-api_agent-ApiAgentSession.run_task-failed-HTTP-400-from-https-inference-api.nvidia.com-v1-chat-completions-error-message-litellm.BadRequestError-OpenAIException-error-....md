---
id: TASK-442
title: >-
  [backend:api_agent] ApiAgentSession.run_task failed: HTTP 400 from
  https://inference-api.nvidia.com/v1/chat/completions:
  {"error":{"message":"litellm.BadRequestError: OpenAIException -
  {\"error\":{...
status: Done
assignee: []
created_date: '2026-06-03 21:02'
updated_date: '2026-06-04 17:31'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 78000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.BadRequestError: OpenAIException - {\"error\":{\"message\":\"You passed 98305 input tokens and requested 32768 output tokens. However, the model's context length is only 131072 tokens, resulting in a maximum input length of 98304 tokens. Please reduce the length of the input prompt. (parameter=input_tokens, value=98305)\",\"type\":\"BadRequestError\",\"param\":\"input_tokens\",\"code\":400}}. Received Model Group=nvidia/nvidia/nemotron-3-super-v3\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-04 17:15

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2
author: oompah
created: 2026-06-04 17:15

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3
author: oompah
created: 2026-06-04 17:16

Agent completed successfully in 48s (1201 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4
author: oompah
created: 2026-06-04 17:16

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 14, Tool calls: 7
- Tokens: 8 in / 1.2K out [1.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 48s
- Log: TASK-442__20260604T171539Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5
author: oompah
created: 2026-06-04 17:20

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6
author: oompah
created: 2026-06-04 17:20

Focus: Duplicate Investigator
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7
author: oompah
created: 2026-06-04 17:21

Agent completed successfully in 67s (2074 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8
author: oompah
created: 2026-06-04 17:21

Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 15, Tool calls: 9
- Tokens: 10 in / 2.1K out [2.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 7s
- Log: TASK-442__20260604T172017Z.jsonl
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
duplicate-of:TASK-432 - Same HTTP 400 context-window-exceeded error on nvidia/nemotron-3-super-v3. TASK-432 already fixed this by expanding _is_context_window_error to detect the litellm.BadRequestError variant.
<!-- SECTION:FINAL_SUMMARY:END -->
