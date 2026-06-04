---
id: TASK-432
title: >-
  [backend:api_agent] ApiAgentSession.run_task failed: HTTP 400 from
  https://inference-api.nvidia.com/v1/chat/completions:
  {"error":{"message":"litellm.BadRequestError: OpenAIException -
  {\"error\":{...
status: Done
assignee: []
created_date: '2026-06-03 17:53'
updated_date: '2026-06-04 16:53'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 68000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/v1/chat/completions: {"error":{"message":"litellm.BadRequestError: OpenAIException - {\"error\":{\"message\":\"You passed 98305 input tokens and requested 32768 output tokens. However, the model's context length is only 131072 tokens, resulting in a maximum input length of 98304 tokens. Please reduce the length of the input prompt. (parameter=input_tokens, value=98305)\",\"type\":\"BadRequestError\",\"param\":\"input_tokens\",\"code\":400}}. Received Model Group=nvidia/nvidia/nemotron-3-super-v3\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: a1b2c3d4-e5f6-7890-abcd-ef1234567890
author: oompah
created: 2026-06-04T16:45:00Z

UNDERSTANDING: TASK-432 is the original issue (created 2026-06-03 17:53). TASK-435/438/440/442 are exact duplicates with identical errors (same model, same token counts). Root cause: ApiAgentSession sends 98305 input tokens + requests 32768 output tokens = 131073 total, which exceeds nemotron-3-super-v3 max context of 131072 by 1. Fix needed: truncate the conversation history or reduce max_tokens when approaching the model's context limit. Investigating api_agent code now.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed: expanded _is_context_window_error and _CONTEXT_WINDOW_RE to detect the NVIDIA litellm.BadRequestError variant (error body contains 'context length is only N tokens' instead of 'ContextWindowExceededError'). The existing recovery path (prune messages + retry) now fires for both error shapes. Added unit tests for detection/extraction and an integration test for the full _call_api recovery path. Closed duplicates TASK-435, TASK-438, TASK-440, TASK-442.
<!-- SECTION:FINAL_SUMMARY:END -->
