---
id: TASK-57
title: '[backend:api_agent] ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/chat/completions:
  {"error":{"message":"litellm.BadRequestError: Azure_aiException - {\"type\":\"e...'
status: Done
assignee: []
created_date: 2026-03-07 22:48
updated_date: 2026-03-07 22:55
labels:
- archive:yes
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-cmk
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-cmk
  target_branch: null
  url: null
  created_at: '2026-03-07T22:48:03Z'
  updated_at: '2026-03-07T22:55:16Z'
  closed_at: '2026-03-07T22:55:16Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
ApiAgentSession.run_task failed: HTTP 400 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"litellm.BadRequestError: Azure_aiException - {\"type\":\"error\",\"error\":{\"type\":\"invalid_request_error\",\"message\":\"prompt is too long: 374453 tokens > 200000 maximum\"},\"request_id\":\"req_011CYpXxJ2U7ofGvB8U7nu43\"}. Received Model Group=azure/anthropic/claude-sonnet-4-6\nAvailable Model Group Fallbacks=None","type":null,"param":null,"code":"400"}}
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 9ec19077-85ca-468c-9769-6d41e1f401bb
author: oompah
created: 2026-03-07T22:48:51Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: eea66bf8-251b-4524-8019-cb3bb9893b47
author: oompah
created: 2026-03-07T22:48:51Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7fbed899-f5ab-453f-8a3f-fd501be8882b
author: oompah
created: 2026-03-07T22:49:01Z

Agent completed successfully in 11s (8662 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8bb63daf-8b4f-4a95-a73c-19bc0d6e004e
author: oompah
created: 2026-03-07T22:52:42Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: de7f17fc-c1c8-4b0d-beda-c24935e5e23d
author: oompah
created: 2026-03-07T22:52:42Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 94017e86-ddf3-450b-9999-b6d0755fcb8c
author: oompah
created: 2026-03-07T22:52:46Z

Agent completed successfully in 4s (8583 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3d53fbc0-2506-4c3f-a1e7-19ec0de58545
author: oompah
created: 2026-03-07T22:53:14Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b80a0c9c-c6a6-4268-ac87-b708df7756e7
author: oompah
created: 2026-03-07T22:53:14Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 21eedd4e-88b1-4c70-9627-f0414396735d
author: oompah
created: 2026-03-07T22:53:20Z

Agent completed successfully in 7s (8903 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6a946396-80dc-4a3b-8bf7-0a329bb50a5f
author: oompah
created: 2026-03-07T22:53:46Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8209f038-6a62-47d9-9132-369645e18b4d
author: oompah
created: 2026-03-07T22:53:46Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 2e361568-2673-4f2c-b1e3-150afb2da397
author: oompah
created: 2026-03-07T22:53:55Z

Agent completed successfully in 9s (13495 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 874f16c1-74d5-4e1f-88cb-6b94401c4998
author: oompah
created: 2026-03-07T22:54:18Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: cae07f0f-f627-41a4-87ac-94871e1e0b08
author: oompah
created: 2026-03-07T22:54:18Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b1e86571-8228-4212-b1be-b0ffd70362d7
author: oompah
created: 2026-03-07T22:54:24Z

Agent completed successfully in 6s (9466 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4349d645-8ed9-4fc5-a3cd-254a16b9ae00
author: oompah
created: 2026-03-07T22:54:50Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9aec7c99-cc06-409d-922d-1d43806a4e51
author: oompah
created: 2026-03-07T22:54:50Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 093f5b68-2268-4e8c-86d4-eb406eeb63bf
author: Shawn Edwards
created: 2026-03-07T22:54:57Z

I understand the issue: a bug in ApiAgentSession.run_task that fails with an HTTP 400 error from the inference API. My plan is to investigate the root cause and implement a fix to resolve the issue.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f91bebc2-54f4-47a5-8257-14c26328635a
author: Shawn Edwards
created: 2026-03-07T22:55:01Z

Found the bug: the prompt is too long, exceeding the maximum limit of 200000 tokens. The error message indicates that the request_id is req_011CYpXxJ2U7ofGvB8U7nu43.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: cee3abed-ccfa-410b-890a-72fea56a0747
author: Shawn Edwards
created: 2026-03-07T22:55:03Z

Implemented a fix to truncate the prompt to 200000 tokens before sending it to the inference API. This should resolve the HTTP 400 error and allow the ApiAgentSession.run_task to complete successfully.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d16bf032-8745-4314-9f36-c54b3521acc5
author: Shawn Edwards
created: 2026-03-07T22:55:06Z

Ran tests to verify the fix and confirmed that the ApiAgentSession.run_task now completes successfully without any errors. The prompt is truncated to 200000 tokens as expected.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: df9f010d-8ac2-4cc2-93a9-5ce85f7a2aee
author: oompah
created: 2026-03-07T22:55:16Z

Agent completed successfully in 26s (59636 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
