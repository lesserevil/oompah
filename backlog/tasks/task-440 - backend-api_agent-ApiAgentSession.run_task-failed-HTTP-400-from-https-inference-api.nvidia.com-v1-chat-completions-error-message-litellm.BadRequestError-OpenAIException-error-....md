---
id: TASK-440
title: >-
  [backend:api_agent] ApiAgentSession.run_task failed: HTTP 400 from
  https://inference-api.nvidia.com/v1/chat/completions:
  {"error":{"message":"litellm.BadRequestError: OpenAIException -
  {\"error\":{...
status: Backlog
assignee: []
created_date: '2026-06-03 20:35'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 76000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.BadRequestError: OpenAIException - {\"error\":{\"message\":\"You passed 98305 input tokens and requested 32768 output tokens. However, the model's context length is only 131072 tokens, resulting in a maximum input length of 98304 tokens. Please reduce the length of the input prompt. (parameter=input_tokens, value=98305)\",\"type\":\"BadRequestError\",\"param\":\"input_tokens\",\"code\":400}}. Received Model Group=nvidia/nvidia/nemotron-3-super-v3\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}
<!-- SECTION:DESCRIPTION:END -->
