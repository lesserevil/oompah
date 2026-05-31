---
id: TASK-133
title: '[backend:api_agent] ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/chat/completions:
  {"error":{"message":"litellm.BadRequestError: Azure_aiException - {\"type\":\"e...'
status: Done
assignee: []
created_date: 2026-03-11 01:00
updated_date: 2026-03-11 15:50
labels:
- archive:yes
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-611
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-611
  target_branch: null
  url: null
  created_at: '2026-03-11T01:00:19Z'
  updated_at: '2026-03-11T15:50:09Z'
  closed_at: '2026-03-11T15:50:09Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"litellm.BadRequestError: Azure_aiException - {\"type\":\"error\",\"error\":{\"type\":\"invalid_request_error\",\"message\":\"prompt is too long: 948538 tokens > 200000 maximum\"},\"request_id\":\"req_011CYvPTzrv1gLt4yM4BKvXo\"}. Received Model Group=azure/anthropic/claude-sonnet-4-6\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 56c9346e-d7ae-411f-ac5d-223d99be16d8
author: oompah
created: 2026-03-11T13:14:08Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e39c52d0-15cd-42d3-bd91-53720af3e354
author: oompah
created: 2026-03-11T13:14:09Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 162750f7-a7ff-4083-bb2c-113fbc5385b3
author: oompah
created: 2026-03-11T13:14:20Z

Agent completed successfully in 12s (10808 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 47298d94-678d-4c6e-aca0-7fb0f8e62a82
author: oompah
created: 2026-03-11T13:14:20Z

Agent completed without closing this issue (12s (10808 tokens)). Escalating from 'default' to 'quick'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 316575a4-50c8-4cd8-a02a-d5b643a06035
author: oompah
created: 2026-03-11T13:14:31Z

Agent dispatched (profile: quick)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8d99861f-ad77-43a9-8fbf-0c8511953ef9
author: oompah
created: 2026-03-11T13:14:31Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2ddf4ac7-5b77-4fad-a209-ad3f50fa8e34
author: oompah
created: 2026-03-11T13:14:40Z

Agent completed successfully in 10s (11288 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: ddcf2553-16d6-491f-8cf2-719ff7265128
author: oompah
created: 2026-03-11T13:14:40Z

Agent completed without closing this issue (10s (11288 tokens)). Escalating from 'quick' to 'standard'. Retrying in 20s (2/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d321a603-0d18-4bff-8ad4-2f93f4b9bdc6
author: oompah
created: 2026-03-11T14:14:48Z

Retrying (attempt #16, agent: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b9f74e3a-6b0b-49a2-b26f-96a5d3807d82
author: oompah
created: 2026-03-11T14:14:49Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8ebceb04-92a8-4402-ac9e-723337074669
author: oompah
created: 2026-03-11T14:14:53Z

Agent completed successfully in 6s (12126 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 144ab918-8f97-4091-80f1-5ccebca71f56
author: oompah
created: 2026-03-11T14:14:54Z

Agent completed 3 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
