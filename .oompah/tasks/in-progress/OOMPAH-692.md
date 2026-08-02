---
id: OOMPAH-692
type: feature
status: In Progress
priority: 1
title: Version authoritative dashboard state in the WebSocket protocol
parent: OOMPAH-691
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T02:01:46.836436Z'
updated_at: '2026-08-02T02:07:31.519698Z'
work_branch: epic-OOMPAH-691--task-OOMPAH-692
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 153bc7b698bb721a82b44c0269db3f75f95d31ee5222eb47e476fa3533506fcf
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T02:05:49.659698+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Reviewed the current state-branch task records. OOMPAH-691\
    \ is the parent epic; OOMPAH-693 is a dependent full-sync API, OOMPAH-694 the\
    \ dependent browser convergence logic, and OOMPAH-695 downstream fault-injection\
    \ coverage\u2014each explicitly depends on OOMPAH-692\u2019s server-side versioning\
    \ contract. Closest terminal work, OOMPAH-690 (delivery/heartbeat reliability)\
    \ and OOMPAH-674 (authenticated bootstrap enrichment), is merged and does not\
    \ implement revisions, per-connection sequences, or epoch semantics."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d68433e1-e200-447e-8a06-a0fb5b3366e6
oompah.work_branch: epic-OOMPAH-691--task-OOMPAH-692
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-691--task-OOMPAH-692
  base_branch: epic-OOMPAH-691
  base_sha: 6252b5434f392b74de9703a9fc8dca1951dfeaca
  updated_at: '2026-08-02T02:06:13.581758+00:00'
oompah.task_costs:
  total_input_tokens: 852710
  total_output_tokens: 3464
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 852710
      output_tokens: 3464
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 852710
    output_tokens: 3464
    cost_usd: 0.0
    recorded_at: '2026-08-02T02:05:49.658695+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-692__20260802T020428Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: duplicate_detector
    source_branch: epic-OOMPAH-691--task-OOMPAH-692
    source_sha: 6252b5434f392b74de9703a9fc8dca1951dfeaca
    completed_at: '2026-08-02T02:05:49.672261+00:00'
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
author: oompah
created: 2026-08-02 02:05
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 10
- Tokens: 852.7K in / 3.5K out [856.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 35s
- Log: OOMPAH-692__20260802T020428Z.jsonl
---
author: oompah
created: 2026-08-02 02:06
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 02:06
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-02 02:06
---
**Understanding:** This task requires implementing server-side WebSocket protocol versioning to track authoritative dashboard state freshness. The scope includes:
1. Protocol envelope with version, epoch (service_instance_id), per-connection delivery sequence, state revision, issue revision
2. Advancing revisions whenever state/issue snapshots change
3. Concurrency-safe counters across observer threads and API loop
4. Trailing-edge coalescing instead of leading-edge dropping
5. Updated tests for monotonic revisions, contiguous sequences, epoch reset, concurrent callbacks

This appears to be primarily backend (server.py, orchestrator.py) and protocol work. As a Frontend Developer, I need to assess if there's a UI component or if this should be handed to a backend specialist.

Starting codebase exploration now.
---
author: oompah
created: 2026-08-02 02:07
---
HANDOFF: This task requires backend implementation, not frontend work.

**Discovery:** Explored the codebase and found:
- WebSocket communication is handled in oompah/server.py with global state (_ws_clients, throttles, snapshots)
- Current messages have types: 'state', 'issues', 'pong', 'console_event'
- Existing fields include http_auth, build_id, service_instance_id
- Tests are in tests/test_ws_lifecycle.py

**What needs doing (backend):**
1. Add protocol version, epoch, delivery_seq, state_revision, issue_revision to message envelopes
2. Advance state_revision on state snapshot updates via _update_state_snapshot
3. Advance issue_revision on issue snapshot invalidation/rebuild
4. Make counters concurrency-safe across observer threads and API loop
5. Replace leading-edge dropping with trailing-edge coalescing
6. Update protocol documentation in plans/
7. Add tests for: monotonic revisions, contiguous sequences, epoch reset, concurrent callbacks

**Relevant code locations:**
- oompah/server.py: _broadcast(), _on_orchestrator_change(), _on_state_only_change(), _throttled_broadcast_issues(), message construction
- oompah/orchestrator.py: notification paths and state snapshot updates
- tests/test_ws_lifecycle.py: existing lifecycle tests
- plans/: protocol documentation (needs creation/update)

**Why not frontend:** All implementation is server-side protocol work. Dashboard.tsx will eventually consume the versioned data, but no UI changes are required for this phase.

**Recommended next focus:** Backend developer to implement protocol versioning and freshness contract.
---
<!-- COMMENTS:END -->
