---
id: OOMPAH-325
type: task
status: Backlog
priority: 1
title: Add GitLab project-hook lifecycle and webhook event parity
parent: OOMPAH-318
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-21T20:34:27.176966Z'
updated_at: '2026-07-21T20:34:27.176966Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan reference: plans/gitlab-forge-parity.md, Webhooks, UI, bootstrap, and operations.

Implement GitLab Project Hook management separate from the gh-webhook forwarder. Require/configure OOMPAH_GITLAB_WEBHOOK_PUBLIC_URL, create/reconcile/remove GitLab hooks with a per-project secret, and record hook health. Extend webhook parsing and server handling for Push Hook, Merge Request Hook, Issue Hook, Note Hook, Pipeline Hook, Job Hook, and label-relevant events. Normalize all into WebhookEvent/EventBus and retain polling fallback.

Do not manage reverse proxies or tunnels; the operator provides public HTTPS reachability.

Tests:
- Hook API create/update/delete/reconciliation and redacted error fixtures.
- Token validation, project matching, event normalization, delivery deduplication, and health degradation/recovery.
- Existing gh webhook forwarder tests remain unchanged.

Acceptance criteria:
- A GitLab project receives authenticated event-driven MR, issue, and pipeline updates, with clear polling-fallback alerts on failure.
- No webhook secret or token appears in logs/API responses.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

