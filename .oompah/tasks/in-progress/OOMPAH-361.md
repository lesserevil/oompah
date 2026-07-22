---
id: OOMPAH-361
type: task
status: In Progress
priority: null
title: 'OOMPAH-322 follow-up: Expand parse_gitlab_webhook to handle push/issue/note/pipeline/job
  event types'
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T01:55:04.171330Z'
updated_at: '2026-07-22T03:32:38.857262Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: c65238ac-cd42-49db-8b7a-9b9f318ad994
---
## Summary

During rebase of epic-OOMPAH-318 onto main (OOMPAH-353), uncommitted WIP tests were found that test broader GitLab webhook event handling in parse_gitlab_webhook (oompah/webhooks.py). Currently, parse_gitlab_webhook() only handles 'Merge Request Hook' and returns None for all other event types.

The WIP tests (reverted in commit 60e5f1eb9 on epic-OOMPAH-318) expected:
- Push Hook → WebhookEvent(action='pushed', target_branch=..., author=...)
- Issue Hook → WebhookEvent(action=..., issue_number=..., title=...)
- Note Hook → WebhookEvent(action=..., issue_number=..., comment_id=...)
- Pipeline Hook → WebhookEvent(action=..., target_branch=...)
- Job Hook → WebhookEvent(action=..., target_branch=...)
- Label Update → retains label_name for downstream invalidation

Also needed: test_server_webhooks.py::TestGitLabWebhookEndpoint::test_push_event_is_processed_and_refreshes_tracked_branch — the GitLab webhook endpoint should process push events and refresh the tracked branch.

Implementation scope:
1. Extend parse_gitlab_webhook() in oompah/webhooks.py to handle Push Hook, Issue Hook, Note Hook, Pipeline Hook, Job Hook
2. Ensure the server endpoint (oompah/server.py around line 13474) processes these new event types
3. Re-add and pass the tests from the reverted commit (tests/test_webhooks.py TestParseGitLabWebhook, tests/test_server_webhooks.py TestGitLabWebhookEndpoint)
4. Run make test to verify

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 03:32
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 03:32
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
