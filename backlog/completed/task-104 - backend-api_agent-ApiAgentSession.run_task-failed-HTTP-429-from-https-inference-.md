---
id: TASK-104
title: '[backend:api_agent] ApiAgentSession.run_task failed: HTTP 429 from https://inference-api.nvidia.com/chat/completions:
  {"error":{"message":"{''error'': ''Priority-based rate limit exceeded. Priority:
  d...'
status: Done
assignee: []
created_date: 2026-03-08 20:29
updated_date: 2026-03-08 20:31
labels:
- archive:yes
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-ipv
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-ipv
  target_branch: null
  url: null
  created_at: '2026-03-08T20:29:40Z'
  updated_at: '2026-03-08T20:31:37Z'
  closed_at: '2026-03-08T20:31:37Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 429 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"{'error': 'Priority-based rate limit exceeded. Priority: dev, Rate limit type: tokens, Remaining: -354884, Model saturation: 72.1%'}","type":"None","param":"None","code":"429"}}
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
