---
id: OOMPAH-598
type: bug
status: Backlog
priority: 1
title: Detect and deliver standalone Ready to Integrate tasks without PRs
parent: OOMPAH-587
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:15:29.695490Z'
updated_at: '2026-07-30T14:15:29.695490Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Add reconciliation for standalone tasks whose tracker state is Ready to Integrate and whose branch is pushed, but which have neither an active integration execution nor an open PR. Select the configured delivery mechanism deterministically, enqueue/open it idempotently, and alert on genuinely undeliverable rows. Recover the current OOMPAH-574, OOMPAH-575, OOMPAH-576, and OOMPAH-581 rows. Do not create duplicate PRs or bypass the configured full gate. Relevant areas include landing reconciliation, integration queue, review creation, webhook state, and release-delivery status.

Tests

Cover pushed standalone branch, missing branch, existing open/closed PR, existing queue row, duplicate ticks, restart, gate failure/retry, and successful merge/audit. Run focused tests and make test.

Acceptance criteria

A pushed standalone Ready task cannot remain invisible with no PR/queue activity beyond the reconciliation interval; all four current rows obtain a valid delivery path or explicit actionable failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

