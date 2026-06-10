---
id: TASK-463.2
title: Invalidate caches and request refresh from GitHub task webhooks
status: In Progress
assignee: []
created_date: '2026-06-08 17:58'
updated_date: '2026-06-10 00:53'
labels:
  - task
  - github-issues
  - tracker-migration
dependencies:
  - TASK-463.1
references:
  - plans/github-issues-tracker-migration.md
modified_files:
  - oompah/server.py
  - oompah/orchestrator.py
  - tests/test_webhooks.py
parent_task_id: TASK-463
priority: high
ordinal: 153000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Wire GitHub task webhook events to invalidate issue list, detail, comment, branch-to-issue, and review caches. Trigger orchestrator refresh only when the event can affect dispatch, status, comments, or review reconciliation.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dashboard updates promptly after GitHub-side status/comment edits.
- [ ] #2 Webhook storms do not trigger unnecessary full source syncs.
<!-- AC:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 00:24
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-10 00:26
---
UNDERSTANDING: Duplicate investigation complete — no duplicate found. TASK-423 handled Backlog.md webhook cache invalidation (different mechanism: git post-commit hooks). TASK-421 fixed a review cache bug (unrelated scope). TASK-463.2 is unique: it must wire GitHub Issues API webhook events (parsed in TASK-463.1) to invalidate issue list/detail/comment/branch-to-issue/review caches and trigger orchestrator refresh selectively for events affecting dispatch, status, comments, or review reconciliation. Plan: (1) explore current server.py _handle_webhook_event + orchestrator.py + cache APIs, (2) implement targeted cache invalidation per event type, (3) add selective orchestrator refresh trigger, (4) add/extend tests in test_webhooks.py.
---

author: oompah
created: 2026-06-10 00:42
---
DISCOVERY: Key findings: (1) _handle_webhook_event currently calls request_refresh() and invalidates reviews:all + issues:all for ALL events — wasteful for label events, push to non-tracked branches, projects_v2_item reordering. (2) detail:{project_id}:{issue_number} and comments:{project_id}:{issue_number} caches are NEVER invalidated on webhook receipt. (3) The tracker's ETag/read cache (GitHubIssueTracker._etag_cache) serves as the branch-to-issue read cache and is never invalidated via webhooks. Fix: add _webhook_should_request_refresh(event, project) helper; replace blanket invalidation with targeted per-event-type invalidation; add branch-to-issue cache invalidation via orch._tracker_for_project(project.id).invalidate_read_cache() for issues/pull_request/push events.
---

author: oompah
created: 2026-06-10 00:53
---
IMPLEMENTATION: Modified oompah/server.py with: (1) _handle_webhook_event now does targeted cache invalidation per event type: pull_request/merge_group/Merge_Request_Hook → reviews:all + issues:all; issues → issues:all + detail:{project_id}:{issue_number}; issue_comment → issues:all + comments:{project_id}:{issue_number} + detail:{project_id}:{issue_number}; projects_v2_item → issues:all; label/push events don't touch _api_cache. (2) Added branch-to-issue tracker read cache invalidation via orch._tracker_for_project(project.id).invalidate_read_cache() for issues/pull_request/push events. (3) Added _webhook_should_request_refresh(event, project) helper that returns True only for events affecting dispatch/status/comments/review. Label events and push to non-tracked branches no longer trigger unnecessary orchestrator wakeups. Added 4 new test classes (48 tests): TestWebhookCacheInvalidation, TestWebhookSelectiveRefresh, TestWebhookBranchToIssueCacheInvalidation, TestWebhookShouldRequestRefresh. Total: 64 tests in test_server_webhooks.py.
---
<!-- COMMENTS:END -->
