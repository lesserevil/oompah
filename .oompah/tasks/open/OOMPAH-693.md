---
id: OOMPAH-693
type: feature
status: Open
priority: 1
title: Provide a coherent full dashboard resynchronization response
parent: OOMPAH-691
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-692
labels:
- needs:backend
assignee: null
created_at: '2026-08-02T02:01:48.499285Z'
updated_at: '2026-08-02T02:03:56.882667Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Add the authoritative server operation the dashboard will call after detecting a sequence or revision gap.

Scope:
- Add or extend a WebSocket control action for full synchronization; preserve the existing refresh action as a compatible alias only if its semantics can be made unambiguous.
- Return one versioned full-sync response containing current state, current serialized issues, service epoch, and the exact state/issue revision watermarks represented by the payload.
- Make snapshot assembly race-safe: a mutation during serialization must cause retry/revalidation or a watermark that never claims data newer than the included payload.
- Coalesce duplicate full-sync requests per connection, bound work and payload generation, and return explicit retryable errors without disconnecting a healthy client.
- Preserve project filtering as a client concern unless a project-scoped response has equally strong revision semantics.

Relevant files: oompah/server.py WebSocket endpoint and snapshot caches, serialization helpers, tests/test_ws_lifecycle.py, tests/test_websocket_authenticated_bootstrap.py, and Granian fan-out tests.

Required tests:
- Full sync returns state and issues from a coherent revision watermark.
- A mutation racing snapshot construction cannot produce a falsely current response.
- Concurrent duplicate requests produce bounded server work and one applicable response per client.
- Authentication and multiple-client isolation remain correct.
- Retryable serialization/cache failures are explicit and a later request succeeds.

Acceptance criteria:
- The browser can replace all server-owned dashboard state from one response and know the precise revision from which incremental processing may resume.
- Full synchronization never requires a page reload or a new WebSocket connection.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

