---
id: TASK-471
title: >-
  [backend:api_agent] ApiAgentSession.run_task failed: HTTP 404 from
  https://inference-api.nvidia.com/v1/chat/completions:
  {"error":{"message":"litellm.NotFoundError: NotFoundError: OpenAIException
  -...
status: Backlog
assignee: []
created_date: '2026-06-09 00:40'
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
