---
id: TASK-443
title: >-
  [backend:api_agent] ApiAgentSession.run_task failed: HTTP 400 from
  https://inference-api.nvidia.com/v1/chat/completions:
  {"error":{"message":"litellm.ContextWindowExceededError:
  litellm.BadRequestE...
status: Backlog
assignee: []
created_date: '2026-06-03 21:10'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 79000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.ContextWindowExceededError: litellm.BadRequestError: ContextWindowExceededError: OpenAIException - {\"object\":\"error\",\"message\":\"This model's maximum context length is 262144 tokens. However, your request has 372027 input tokens. Please reduce the length of the input messages. None\",\"type\":\"BadRequestError\",\"code\":400}\nmodel=nvidia/nvidia/Nemotron-3-Nano-30B-A3B. context_window_fallbacks=None. fallbacks=None.\n\nSet 'context_window_fallback' - https://docs.litellm.ai/docs/routing#fallbacks. Received Model Group=nvidia/nvidia/Nemotron-3-Nano-30B-A3B\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}
<!-- SECTION:DESCRIPTION:END -->
