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
labels: []
assignee: null
created_at: '2026-08-02T02:01:48.499285Z'
updated_at: '2026-08-02T02:06:26.566022Z'
work_branch: epic-OOMPAH-691--task-OOMPAH-693
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 2b9546b2a408f9fde6a28c0895d88ee2692a4b540b9028f1290807fef0d01041
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: d8bc774a-6850-4bd4-a28f-63ec279130dc
  claim_owner: a99e28f1-69ee-4f52-9672-996f40b2018d
  claimed_at: '2026-08-02T02:06:11.261487+00:00'
  claim_expires_at: '2026-08-02T02:36:11.261487+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 665a3a30-6a9c-47d8-858a-f28193fb5b91
oompah.work_branch: epic-OOMPAH-691--task-OOMPAH-693
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-691--task-OOMPAH-693
  base_branch: epic-OOMPAH-691
  base_sha: 6252b5434f392b74de9703a9fc8dca1951dfeaca
  updated_at: '2026-08-02T02:06:21.447611+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 02:06
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-02 02:06
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
