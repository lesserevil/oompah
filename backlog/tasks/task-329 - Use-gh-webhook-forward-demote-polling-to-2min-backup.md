---
id: TASK-329
title: Use gh webhook forward; demote polling to 2min backup
status: To Do
assignee: []
created_date: 2026-05-04 23:54
updated_date: 2026-05-05 03:45
labels:
- decomposed
- feature
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: feature
beads:
  id: oompah-zlz_2-1a7
  state: deferred
  parent_id: null
  dependencies: []
  branch_name: oompah-zlz_2-1a7
  target_branch: null
  url: null
  created_at: '2026-05-04T23:54:52Z'
  updated_at: '2026-05-05T03:45:50Z'
  closed_at: null
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Currently the orchestrator polls GitHub every 30s per project (list_open_reviews + list_merged_branches in orchestrator.py:1021/1049), which is wasteful and burns rate limit. Replace the primary signal path with 'gh webhook forward' streaming GitHub webhooks to the existing local endpoint /api/v1/webhooks/github (server.py:1890), and demote the polling loop to a safety-net backup that runs only if webhook deliveries are stale.

Scope:
- Supervise a 'gh webhook forward' subprocess alongside the oompah server (sibling to orchestrator) targeting http://localhost:8080/api/v1/webhooks/github for each configured GitHub project.
- Track per-project last-webhook-delivery timestamp; treat the webhook channel as healthy if a delivery was received recently.
- Change OOMPAH_POLL_INTERVAL_MS / full_sync_interval_ms default from 30000 to 120000 (2 minutes) in config.py:231-232 and models.py:288.
- When webhook is healthy for a project, the periodic poll can be skipped or run at a longer cadence; when unhealthy/stale, fall back to the 2-minute poll.
- Keep GitLab path unchanged (no equivalent gh-style forwarder).

Acceptance:
- New default poll interval is 2 minutes.
- gh webhook forward process is launched and managed by oompah for GitHub projects.
- Webhook deliveries reduce or eliminate periodic polling when healthy.
- If gh webhook forward dies or webhooks stop arriving, polling resumes as backup.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019df579-0dde-777a-a780-a535b45acfed
author: oompah
created: 2026-05-05T00:10:45Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df579-2079-7aae-80a0-438853735519
author: oompah
created: 2026-05-05T00:10:49Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df57a-7543-72d2-8777-c3f85869cfc2
author: oompah
created: 2026-05-05T00:12:17Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df57a-9a04-7dde-8489-910ffd0bdc82
author: oompah
created: 2026-05-05T00:12:26Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df57e-3b71-71dc-bf41-29acb7a940bf
author: oompah
created: 2026-05-05T00:16:24Z

Rate limited by API. Pausing all dispatch for 120s. Retrying in 120s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df580-2e4e-7cf0-bdcd-5fbacea2ce00
author: oompah
created: 2026-05-05T00:18:32Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df580-544f-7501-bd92-1a47eb84a650
author: oompah
created: 2026-05-05T00:18:41Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df585-1d36-7f23-9dbb-2fa6b89b16ee
author: oompah
created: 2026-05-05T00:23:55Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df585-2677-729f-b7b6-e2447c23affc
author: oompah
created: 2026-05-05T00:23:57Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df58b-186a-7079-8d9d-6d75c64409df
author: oompah
created: 2026-05-05T00:30:27Z

Agent stalled 1 time(s) (392s (354843 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df58b-9563-771c-aa61-07e234165e2f
author: oompah
created: 2026-05-05T00:30:59Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df58b-9ed1-77e7-9038-64d8cae1cf9a
author: oompah
created: 2026-05-05T00:31:01Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df58f-3554-7ef0-82d8-0b79766b3012
author: oompah
created: 2026-05-05T00:34:56Z

Issue has failed 2 time(s). Attempting auto-decomposition into smaller tasks.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df58f-ce5b-732c-b025-09b208d096e8
author: oompah
created: 2026-05-05T00:35:36Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df58f-d809-7242-be08-f201fe33157d
author: oompah
created: 2026-05-05T00:35:38Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df590-dd36-7ab6-9395-46434f45129c
author: oompah
created: 2026-05-05T00:36:45Z

Agent failed: HTTP 400 from http://100.64.0.3:8888/v1/chat/completions: {"error":{"message":"This model's maximum context length is 196608 tokens. However, you requested 32768 output tokens and your prompt contains at least 163841 input tokens, for a total of at least 196609 tokens. Please reduce the length of the input prompt or the number of requested output tokens. (parameter=input_tokens, value=163841)","type":"BadRequestError","param":"input_tokens","code":400}}. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df591-3547-7182-b0e7-aa8e559c50ed
author: oompah
created: 2026-05-05T00:37:08Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df591-8641-7af0-9e8c-6c581e1dc79f
author: oompah
created: 2026-05-05T00:37:28Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59d-1152-7c63-a131-0f6c8b8642c9
author: oompah
created: 2026-05-05T00:50:05Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59d-3445-74c2-8044-5be7ab84581f
author: oompah
created: 2026-05-05T00:50:14Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59f-7bef-7d00-9a66-483f0c91bfb9
author: oompah
created: 2026-05-05T00:52:43Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df59f-87c0-7bfa-813b-1d7ccda84fc6
author: oompah
created: 2026-05-05T00:52:46Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5b1-58ea-70de-8c92-404c85176a1a
author: oompah
created: 2026-05-05T01:12:14Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5b1-6f6f-7975-8cc2-05ba5997456d
author: oompah
created: 2026-05-05T01:12:20Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5b6-e90b-729f-a71b-7840e296e9b6
author: oompah
created: 2026-05-05T01:18:18Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df5b6-eb00-7cd9-b211-f7cd0eb2e8a2
author: oompah
created: 2026-05-05T01:18:19Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df60f-c3e5-7947-94d1-c016c53015c5
author: oompah
created: 2026-05-05T02:55:22Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df60f-cb1b-7756-8ab9-8f24b6a43114
author: oompah
created: 2026-05-05T02:55:23Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df60f-f0e3-7510-89a0-56e1a38b9152
author: oompah
created: 2026-05-05T02:55:33Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df610-2ecd-7733-8723-7013e5b1d3d2
author: oompah
created: 2026-05-05T02:55:49Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df610-349a-71a5-a9cb-9ae0f214e5a1
author: oompah
created: 2026-05-05T02:55:50Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df610-456b-7718-ac11-c393b2072e69
author: oompah
created: 2026-05-05T02:55:55Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df610-defd-77d7-a282-08dc43fd4d81
author: oompah
created: 2026-05-05T02:56:34Z

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df610-e257-762e-9e7a-e04342414f94
author: oompah
created: 2026-05-05T02:56:35Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df611-0bc9-7518-b34c-d1ba0119b006
author: oompah
created: 2026-05-05T02:56:46Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 40s (attempt #3)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df612-2a86-7a12-9e48-b8324af23e72
author: oompah
created: 2026-05-05T02:57:59Z

Retrying (attempt #3, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df612-8d23-7363-9ade-64610ae53eba
author: oompah
created: 2026-05-05T02:58:24Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df612-a930-7c21-a55a-740128e2f1b0
author: oompah
created: 2026-05-05T02:58:31Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 80s (attempt #4)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df614-cd0a-7ac5-b5b4-10be0f3f7244
author: oompah
created: 2026-05-05T03:00:52Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df614-d061-7b6d-8a27-45b3680f107c
author: oompah
created: 2026-05-05T03:00:52Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df614-d6f5-7153-aeae-900417b342df
author: oompah
created: 2026-05-05T03:00:54Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df615-75c1-7c0a-99be-47827e12ede0
author: oompah
created: 2026-05-05T03:01:35Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df615-79a5-7d2f-b1cf-861b4c83c951
author: oompah
created: 2026-05-05T03:01:36Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df615-8b68-761e-8102-245806f1d58d
author: oompah
created: 2026-05-05T03:01:40Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df615-ec9c-7bcb-9b1f-29ec2015321b
author: oompah
created: 2026-05-05T03:02:05Z

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df615-f4df-7d59-9a0b-7b6f958a76b3
author: oompah
created: 2026-05-05T03:02:07Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df615-fa78-73c4-b7aa-4f8420a41b6a
author: oompah
created: 2026-05-05T03:02:09Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 40s (attempt #3)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df616-c883-798d-ab28-dfea9cd09593
author: oompah
created: 2026-05-05T03:03:02Z

Retrying (attempt #3, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df617-31f8-7c4c-aea8-d95a8e711189
author: oompah
created: 2026-05-05T03:03:29Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 80s (attempt #4)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df618-ac94-74b7-a091-50c01c2ecfa1
author: oompah
created: 2026-05-05T03:05:05Z

Retrying (attempt #4, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df618-b0e0-7603-a6d4-e8044ac6ccb8
author: oompah
created: 2026-05-05T03:05:07Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df618-b689-7c5c-9f29-5bae4eb369d6
author: oompah
created: 2026-05-05T03:05:08Z

Agent failed: URL error for http://100.64.0.3:8888/v1/chat/completions: [Errno 61] Connection refused. Retrying in 160s (attempt #5)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df62a-b16a-77a8-aaa0-9bda005aafe1
author: oompah
created: 2026-05-05T03:24:46Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df62a-b450-7877-9534-59181a7e536f
author: oompah
created: 2026-05-05T03:24:47Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df633-c82f-7e38-8db8-1906591f146e
author: oompah
created: 2026-05-05T03:34:42Z

Agent failed: timed out. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df634-06df-7a8f-bd7d-1bf88c45716b
author: oompah
created: 2026-05-05T03:34:58Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df634-0a2a-79d7-a7cf-97bdfff517e0
author: oompah
created: 2026-05-05T03:34:59Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df63a-91a5-7ce8-9291-db5da3fd5786
author: oompah
created: 2026-05-05T03:42:07Z

Issue has failed 2 time(s). Attempting auto-decomposition into smaller tasks.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019df63d-fd93-74c6-9b73-59c533c38283
author: oompah
created: 2026-05-05T03:45:51Z

Decomposed into 5 sub-tasks. The original issue is too complex because it requires modifying multiple interconnected systems: config defaults, webhook tracking infrastructure, subprocess management, and polling logic. The codebase is large (163k+ tokens in context), causing token limit errors. The agent repeatedly timed out or hit rate limits while trying to implement all changes in a single session. Breaking into focused sub-tasks allows each to be completed in ~20 tool calls with a smaller context window.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
