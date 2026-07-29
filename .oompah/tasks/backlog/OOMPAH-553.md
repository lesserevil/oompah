---
id: OOMPAH-553
type: feature
status: Backlog
priority: 1
title: Deliver coordination messages into live ACP sessions
parent: OOMPAH-550
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T16:23:16.695169Z'
updated_at: '2026-07-29T16:23:16.695169Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Standardize backend message injection through AcpAgentSession. Preserve Claude queue delivery and add safe follow-up-turn draining for Codex subscription/API sessions; support OpenCode when its protocol permits and retain inbox fallback otherwise. A worker must drain queued messages before the session reports success. Delivery is FIFO, idempotent, bounded, observable, and never injected into an already failing or interrupted session.

Tests must cover messages arriving before, during, and after a turn; multiple messages; stop/error races; Codex and Claude follow-up turns; unsupported-backend fallback; and exactly-once delivery across restart boundaries.

Acceptance criteria: supported live agents receive peer messages before exit, unsupported backends lose no messages, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

