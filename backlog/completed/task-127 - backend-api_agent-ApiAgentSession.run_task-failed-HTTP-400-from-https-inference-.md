---
id: TASK-127
title: '[backend:api_agent] ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/chat/completions:
  {"error":{"message":"litellm.BadRequestError: Azure_aiException - {\"type\":\"e...'
status: Done
assignee: []
created_date: 2026-03-09 23:41
updated_date: 2026-03-10 04:11
labels:
- archive:yes
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-6ex
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-6ex
  target_branch: null
  url: null
  created_at: '2026-03-09T23:41:57Z'
  updated_at: '2026-03-10T04:11:35Z'
  closed_at: '2026-03-10T04:11:35Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"litellm.BadRequestError: Azure_aiException - {\"type\":\"error\",\"error\":{\"type\":\"invalid_request_error\",\"message\":\"prompt is too long: 200557 tokens > 200000 maximum\"},\"request_id\":\"req_011CYtPgXWiiwD3SoyQ4f4xX\"}. Received Model Group=azure/anthropic/claude-sonnet-4-6\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 3783d62d-610f-4822-8e48-913417bbeeec
author: oompah
created: 2026-03-10T04:03:52Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d026ef63-64ab-41ce-89a6-a7bfe101a5fc
author: oompah
created: 2026-03-10T04:03:52Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 54cbd9fd-9f00-44fd-b1a7-5e46527aa33a
author: oompah
created: 2026-03-10T04:03:56Z

Agent completed successfully in 5s (10173 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 00553818-1cc6-4943-aea5-a1dea0386348
author: oompah
created: 2026-03-10T04:03:59Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 933ed15c-4e46-472e-90d1-293f04a7d197
author: oompah
created: 2026-03-10T04:04:00Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4768fb14-ceaf-4b3c-a0ca-f04dde3f0dbd
author: oompah
created: 2026-03-10T04:04:06Z

Agent completed successfully in 6s (10484 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c0dabe6b-5228-4316-af64-8c185ac36199
author: oompah
created: 2026-03-10T04:04:07Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3e021076-7568-486f-8f19-e60a761629f0
author: oompah
created: 2026-03-10T04:04:08Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d2b5a9fa-33d4-448f-b0a2-54d41c86a6c8
author: oompah
created: 2026-03-10T04:04:13Z

Agent completed successfully in 6s (10802 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f9fdb311-072b-4130-bd8a-cb1558a01405
author: oompah
created: 2026-03-10T04:04:13Z

Agent completed 3 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
