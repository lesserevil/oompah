---
id: OOMPAH-692
type: feature
status: Open
priority: 1
title: Version authoritative dashboard state in the WebSocket protocol
parent: OOMPAH-691
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T02:01:46.836436Z'
updated_at: '2026-08-02T02:04:25.980188Z'
work_branch: epic-OOMPAH-691--task-OOMPAH-692
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 153bc7b698bb721a82b44c0269db3f75f95d31ee5222eb47e476fa3533506fcf
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 914b4fb0-d665-4262-9685-5cbb234d2c5c
  claim_owner: a99e28f1-69ee-4f52-9672-996f40b2018d
  claimed_at: '2026-08-02T02:04:12.341048+00:00'
  claim_expires_at: '2026-08-02T02:34:12.341048+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9ddf4017-c3a4-4484-8cda-3b6ef0059c39
oompah.work_branch: epic-OOMPAH-691--task-OOMPAH-692
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-691--task-OOMPAH-692
  base_branch: epic-OOMPAH-691
  base_sha: 6252b5434f392b74de9703a9fc8dca1951dfeaca
  updated_at: '2026-08-02T02:04:20.763360+00:00'
---
## Summary

Implement the server-side ordering and freshness contract for dashboard WebSocket data.

Scope:
- Define a documented envelope version with the existing service_instance_id as the stream epoch, a contiguous per-connection delivery sequence, and monotonic authoritative revisions for state and issue snapshots.
- Advance the state revision whenever _update_state_snapshot accepts a newer orchestrator snapshot, including callbacks whose immediate broadcast is throttled. Advance the issue revision whenever an issue snapshot is invalidated/rebuilt.
- Include protocol version, epoch, delivery sequence, state revision, and issue revision as applicable on bootstrap, state, issues, activity, pong, and error/control messages without breaking existing authenticated clients.
- Make counters concurrency-safe across observer threads and the API event loop; define restart/reset and reconnect semantics explicitly in plans/ or adjacent protocol documentation.
- Replace pure leading-edge state dropping with trailing-edge coalescing, or otherwise guarantee that the latest cached snapshot is eventually broadcast when clients remain connected.

Relevant files: oompah/server.py observer/broadcast/cache code, oompah/orchestrator.py notification paths, protocol documentation under plans/, and tests/test_ws_lifecycle.py.

Required tests:
- Multiple authoritative mutations inside the throttle window advance revisions monotonically even if payload broadcasts coalesce.
- The final coalesced state is eventually emitted with the latest revision.
- Per-connection delivery sequences are contiguous and isolated from bootstrap sends to other clients.
- Epoch/revision reset behavior is deterministic across service-instance changes.
- Concurrent callbacks cannot duplicate or regress revisions.

Acceptance criteria:
- The server never labels stale state with a current revision.
- A client can distinguish transport-message gaps from authoritative state-generation gaps.
- Existing WebSocket fan-out, authentication, console, and issue-throttle tests remain green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 02:04
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-02 02:04
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
