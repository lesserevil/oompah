---
id: OOMPAH-552
type: feature
status: Backlog
priority: 0
title: Add worker-scoped coordination API, CLI, and tools
parent: OOMPAH-550
children: []
blocked_by:
- OOMPAH-551
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:23:15.200331Z'
updated_at: '2026-07-29T16:24:46.296971Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Add authenticated endpoints and CLI commands for oompah coordinate peers, inbox, send, and checkpoint. Extend task handoff capabilities without exposing operator credentials. A worker may read its own inbox and message only server-suggested peers in the same managed project; system automation may publish validated notices. Surface messages in a separate Oompah coordination timeline rather than external tracker comments.

Tests must cover capability scope, expiry, cross-project and non-peer rejection, message validation, pagination, idempotency, CLI request construction, direct ACP tool routing, and OpenAPI/MCP exposure policy.

Acceptance criteria: every spawned worker can safely use the coordination surface, unauthorized routing is rejected without secret leakage, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:24
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
<!-- COMMENTS:END -->
