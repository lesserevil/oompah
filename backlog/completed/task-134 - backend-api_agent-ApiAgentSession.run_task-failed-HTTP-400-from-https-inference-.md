---
id: TASK-134
title: '[backend:api_agent] ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/chat/completions:
  {"error":{"message":"litellm.BadRequestError: Azure_aiException - {\"type\":\"e...'
status: Done
assignee: []
created_date: 2026-03-11 03:24
updated_date: 2026-03-11 13:14
labels:
- archive:yes
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-nl0
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-nl0
  target_branch: null
  url: null
  created_at: '2026-03-11T03:24:04Z'
  updated_at: '2026-03-11T13:14:22Z'
  closed_at: '2026-03-11T13:14:22Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"litellm.BadRequestError: Azure_aiException - {\"type\":\"error\",\"error\":{\"type\":\"invalid_request_error\",\"message\":\"prompt is too long: 304979 tokens > 200000 maximum\"},\"request_id\":\"req_011CYvaRs2qnLCEDcpcu7KNM\"}. Received Model Group=azure/anthropic/claude-sonnet-4-6\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 32815015-2cfe-4dbf-847c-ab84704f64ee
author: oompah
created: 2026-03-11T13:14:08Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a6e8a020-97b3-4ad1-890e-a564cb432099
author: oompah
created: 2026-03-11T13:14:09Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 54303616-1f71-4a6e-9db2-7cea50287d17
author: oompah
created: 2026-03-11T13:14:12Z

I understand the issue: ApiAgentSession.run_task failed due to HTTP 400 from https://inference-api.nvidia.com/chat/completions. My plan is to investigate the error and find the root cause of the issue.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b7d6c2a9-dbc6-4c57-9cb9-857a51f37cbd
author: oompah
created: 2026-03-11T13:14:22Z

Agent completed successfully in 14s (21979 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
