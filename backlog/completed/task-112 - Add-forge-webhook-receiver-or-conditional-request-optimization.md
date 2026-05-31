---
id: TASK-112
title: Add forge webhook receiver (or conditional request optimization)
status: Done
assignee: []
created_date: 2026-03-08 21:18
updated_date: 2026-03-08 22:31
labels:
- archive:yes
- ci-fix
- draft
- merged
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-k3d.4
  state: closed
  parent_id: oompah-k3d
  dependencies: []
  branch_name: oompah-k3d.4
  target_branch: null
  url: null
  created_at: '2026-03-08T21:18:47Z'
  updated_at: '2026-03-08T22:31:53Z'
  closed_at: '2026-03-08T22:31:53Z'
parent: TASK-108
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a forge webhook receiver or implement conditional request optimization
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 309159a2-7967-4f85-bdec-661b43234b35
author: oompah
created: 2026-03-08T21:19:04Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 01df301a-6b51-4998-a74f-cd4f5e4026de
author: oompah
created: 2026-03-08T21:19:05Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9491345b-fdb5-43c1-ac26-f951d7444a0f
author: oompah
created: 2026-03-08T21:19:41Z

Agent stalled 1 time(s) (37s (205609 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3320c2b5-480a-4b39-a770-bcced0749242
author: oompah
created: 2026-03-08T21:19:51Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e7a94444-7c7e-4588-a319-66c95657fa0a
author: oompah
created: 2026-03-08T21:19:52Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 943b12fb-5215-4a07-9f93-555232a2c30f
author: oompah
created: 2026-03-08T21:20:44Z

Agent stalled — no productive actions (writes/commands) for 5 consecutive turns (52s (352222 tokens)). Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 159f2220-b5c5-4907-9a12-1c978a260d70
author: oompah
created: 2026-03-08T21:21:04Z

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0fb6e716-00f3-43e3-8d83-0d1c61166996
author: oompah
created: 2026-03-08T21:21:05Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 48f9fb4b-490d-4bf9-93a7-ee7dbed1c0b1
author: oompah
created: 2026-03-08T21:21:29Z

Agent stalled 3 time(s) (24s (196424 tokens)). Escalating from 'standard' to 'deep'. Retrying in 40s (attempt #3)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 3932afbd-6d06-4af8-9fdc-b5ff9a0b4baf
author: oompah
created: 2026-03-08T21:22:09Z

Retrying (attempt #3, agent: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4de89acd-a46e-4906-96e7-f65c6355837b
author: oompah
created: 2026-03-08T21:22:10Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 04f5c7fc-4782-45c7-8a09-3f2ea7e4fe2a
author: oompah
created: 2026-03-08T21:22:58Z

I understand the issue: This is step 4 of the parent epic (oompah-k3d) for making the orchestrator event-driven. The task is to add either a forge webhook receiver OR implement conditional request optimization for forge API calls. Currently, the orchestrator polls GitHub/GitLab APIs every tick (30s) via `_fetch_all_reviews` and `_fetch_all_merged_branches`, making expensive API calls even when nothing has changed.

My plan:
1. Add a webhook receiver endpoint to the server that accepts GitHub/GitLab webhook payloads for PR/MR events
2. When webhooks are received, emit events on the EventBus and trigger a targeted refresh
3. Also implement conditional requests (ETags/If-Modified-Since) on forge API calls as a fallback for when webhooks aren't configured
4. Add a webhook secret validation for security
5. Write comprehensive tests for both webhook receiver and conditional request optimization
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bfbfe616-d47b-4c94-bfb9-2242298b3d8d
author: oompah
created: 2026-03-08T21:24:15Z

Found the relevant code:
- `oompah/scm.py`: SCMProvider ABC with GitHubProvider and GitLabProvider - these do the forge API calls
- `oompah/orchestrator.py`: `_fetch_all_reviews()` and `_fetch_all_merged_branches()` are called every tick (30s) making expensive subprocess/API calls
- `oompah/server.py`: FastAPI server where webhook endpoints will be added
- `oompah/events.py`: EventBus with EventType enum - will need new FORGE_WEBHOOK event type

Implementation plan:
1. Add new EventTypes: FORGE_WEBHOOK_RECEIVED, FORGE_REVIEWS_CHANGED
2. Add webhook receiver endpoints: POST /api/v1/webhooks/github and POST /api/v1/webhooks/gitlab
3. Add webhook secret validation (HMAC-SHA256 for GitHub, token for GitLab)
4. Add conditional request support (ETags) to SCMProvider.list_open_reviews and list_merged_branches
5. Wire webhook events to trigger targeted review refreshes instead of full tick
6. Add webhook_secret field to Project model for per-project configuration
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e5450744-ff61-426b-a10e-dfa7760cd47b
author: oompah
created: 2026-03-08T22:06:53Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4eddbbcc-bd2b-4b97-998b-adb6ffbd6c3b
author: oompah
created: 2026-03-08T22:06:54Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5c631e2a-3e51-4fa3-8cac-db4db8113a1b
author: oompah
created: 2026-03-08T22:08:09Z

Agent stalled 1 time(s) (76s (172103 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8cf3e616-9405-406f-a623-4e696f4ef4a1
author: oompah
created: 2026-03-08T22:08:36Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: bcb074bd-39ce-4b40-b941-7e2242617da3
author: oompah
created: 2026-03-08T22:08:37Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0471e30b-d337-49b5-972e-82883e1d7307
author: oompah
created: 2026-03-08T22:10:52Z

Resuming work on this issue. After thorough codebase review, here is my implementation plan:

1. **Add new EventTypes**: FORGE_WEBHOOK_RECEIVED for when webhooks arrive
2. **Add webhook_secret to Project model**: Per-project webhook secret for validation
3. **Create webhook module (oompah/webhooks.py)**: Webhook payload parsing, HMAC-SHA256 validation (GitHub) and token validation (GitLab), event extraction
4. **Add webhook endpoints to server.py**: POST /api/v1/webhooks/github and POST /api/v1/webhooks/gitlab
5. **Wire to EventBus**: Webhook events trigger targeted refresh via _refresh_requested
6. **Write comprehensive tests**: Cover webhook validation, payload parsing, endpoint routing, and EventBus integration

Starting implementation now.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: c569f21d-a0f5-4f4d-97e4-82f8b5f52c54
author: oompah
created: 2026-03-08T22:19:42Z

Implementation complete and all tests passing (856/856).

Changes made:
1. **oompah/events.py**: Added FORGE_WEBHOOK_RECEIVED EventType
2. **oompah/models.py**: Added webhook_secret field to Project model (with serialization)
3. **oompah/projects.py**: Added webhook_secret to UPDATABLE_FIELDS
4. **oompah/webhooks.py**: New module with:
   - GitHub HMAC-SHA256 signature validation (validate_github_signature)
   - GitLab token validation (validate_gitlab_token)
   - GitHub pull_request payload parsing (parse_github_webhook)
   - GitLab Merge Request Hook payload parsing (parse_gitlab_webhook)
   - Project matching by repo slug (match_project_by_repo)
   - WebhookEvent dataclass for normalized events
5. **oompah/server.py**: Added webhook endpoints:
   - POST /api/v1/webhooks/github — receives GitHub PR events
   - POST /api/v1/webhooks/gitlab — receives GitLab MR events
   - Both validate signatures when webhook_secret is configured
   - Both emit FORGE_WEBHOOK_RECEIVED on EventBus
   - Both invalidate caches and trigger orchestrator refresh
   - webhook_secret added to project update endpoint
6. **tests/test_webhooks.py**: 41 tests for webhook module
7. **tests/test_server_webhooks.py**: 20 tests for server endpoints
8. **tests/test_projects_crud.py**: Updated UPDATABLE_FIELDS test
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0a902515-2eec-4d43-a28d-e013a3d2cf1c
author: oompah
created: 2026-03-08T22:21:51Z

Completed. Delivered forge webhook receiver for GitHub and GitLab:

**New module: oompah/webhooks.py**
- GitHub HMAC-SHA256 signature validation
- GitLab secret token validation
- Payload parsing for PR/MR events into normalized WebhookEvent
- Project matching by repo slug

**Server endpoints:**
- POST /api/v1/webhooks/github — validates X-Hub-Signature-256, parses pull_request events
- POST /api/v1/webhooks/gitlab — validates X-Gitlab-Token, parses Merge Request Hook events
- Both emit FORGE_WEBHOOK_RECEIVED on EventBus and trigger orchestrator refresh
- Non-PR/MR events (push, ping, pipeline) are acknowledged but not processed

**Model changes:**
- webhook_secret field added to Project model (per-project configuration)
- FORGE_WEBHOOK_RECEIVED added to EventType enum

**Tests:** 61 new tests, 856 total passing. Branch pushed.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b211fddb-08c5-4fa0-8858-f13849109e17
author: oompah
created: 2026-03-08T22:22:21Z

Agent completed successfully in 825s (2797780 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d01539e7-ab2b-4e45-8088-dc62df6e1c26
author: oompah
created: 2026-03-08T22:22:24Z

Review created: https://github.com/lesserevil/oompah/pull/43
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: aa7c9eea-55dd-4101-be6c-741638b880c5
author: oompah
created: 2026-03-08T22:24:12Z

YOLO: CI tests failed on review #43. Fix the failing tests so this review can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 28230aef-3675-455b-8fc1-6817c4bf53f3
author: oompah
created: 2026-03-08T22:25:25Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f5ba6fb1-b37a-4363-8d03-3fc9ec7bfa67
author: oompah
created: 2026-03-08T22:25:26Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8c72c9ab-43c6-4655-a54a-3f0f0f2fb56e
author: oompah
created: 2026-03-08T22:28:50Z

Found the failures: 5 tests in TestBlockerHasUnmergedPr class use old method name _blocker_has_unmerged_pr (renamed to _blocker_has_unmerged_review in oompah-k3d.2) and old attribute _unmerged_pr_branches (renamed to _unmerged_review_branches). Fixing the test names to match the current implementation.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6a1e9e9d-6583-45ff-832c-a6f96f00703d
author: oompah
created: 2026-03-08T22:30:17Z

Agent failed: Agent process exited. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 84d09cd3-eeff-48c5-b7d9-ef17412b5922
author: oompah
created: 2026-03-08T22:30:17Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 68505068-ec65-4b93-b579-2b1de12bac2e
author: oompah
created: 2026-03-08T22:30:18Z

Agent failed: Agent process exited. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e8bd3670-5854-481a-a0b7-e7466fd4d648
author: oompah
created: 2026-03-08T22:30:18Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0ce45a8f-e303-450d-828e-48cd5f6683aa
author: oompah
created: 2026-03-08T22:30:19Z

Agent failed: Agent process exited. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 9d287df1-9dc3-47e4-9168-a83f9b6affdf
author: oompah
created: 2026-03-08T22:30:19Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b6e7ec59-e4d2-4a48-881c-e0e5490685cb
author: oompah
created: 2026-03-08T22:31:49Z

Fixed CI test failures: 5 tests in TestBlockerHasUnmergedPr were calling the old method _blocker_has_unmerged_pr (renamed to _blocker_has_unmerged_review in oompah-k3d.2) and setting old attribute _unmerged_pr_branches (now _unmerged_review_branches). Updated tests to use the current method and attribute names. All 948 tests now pass. Pushed fix to branch.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: e33b6433-b8cf-4a7d-9137-8a01b0ce4262
author: oompah
created: 2026-03-08T22:31:54Z

Agent completed successfully in 389s (348100 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
