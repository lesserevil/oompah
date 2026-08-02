---
id: OOMPAH-693
type: feature
status: In Progress
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
updated_at: '2026-08-02T03:32:12.887450Z'
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
  verdict: no_duplicate
  checked_at: '2026-08-02T02:08:00.988418+00:00'
  matched_identifiers: []
  evidence: "I have completed a thorough duplicate investigation across all task states\
    \ and documentation. Here is my summary:\n\n**Search coverage:**\n- All `.oompah/tasks`\
    \ subdirectories: `open/`, `backlog/`, `merged/`, `archived/` (200+ tasks)\n-\
    \ Search patterns: `full.sync|full_sync|resync|resynchron`, `websocket|WebSocket|ws.*action|control.*action`,\
    \ `revision|watermark|snapshot|serializ`, `dashboard|refresh|epoch|sequence.gap`,\
    \ `coherent|synchronization|resynchronization`, `Granian|fan.out|bootstrap|lifecycle`,\
    \ `server.py|test_ws|test_websocket`, and the sibling IDs `OOMPAH-691|692|694|695`\n\
    - `docs/` and `plans/` directories for design/architecture overlap\n\n**Active\
    \ tasks reviewed:**\n- **OOMPAH-281** (Open): Containerized self-hosted GitHub\
    \ Actions runner \u2014 entirely unrelated DevOps topic\n- **OOMPAH-282** (Backlog):\
    \ State branch migration UnicodeEncodeError bug \u2014 entirely unrelated backend\
    \ bug\n\n**Epic sibling tasks** (OOMPAH-692, 694, 695, referenced as coordination\
    \ peers under OOMPAH-691) are not stored in the local tracker and are clearly\
    \ scoped as distinct sibling tasks within the same epic, not duplicates.\n\nNo\
    \ archived or merged task touches WebSocket control actions, dashboard resynchronization,\
    \ revision watermarks, snapshot assembly, or full-sync response structures. The\
    \ topic is entirely new to this codebase at the task-tracking level.\n\n---\n\n\
    Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Exhaustive search across all `.oompah/tasks` states (200+\
    \ tasks in archived, 7 in merged, 1 in open, 1 in backlog) plus `docs/` and `plans/`\
    \ found zero tasks covering WebSocket full-sync responses, dashboard resynchronization,\
    \ revision watermarks, or snapshot assembly. The two active non-terminal tasks\
    \ (OOMPAH-281: self-hosted runner; OOMPAH-282: unicode migration bug) are completely\
    \ unrelated in topic and scope. The referenced sibling tasks (OOMPAH-692, 694,\
    \ 695) are coordination peers under the same epic (OOMPAH-691), not duplicates"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: eafd73e0-4ff2-473f-a88d-f5f00a5701e1
oompah.work_branch: epic-OOMPAH-691--task-OOMPAH-693
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-691--task-OOMPAH-693
  base_branch: epic-OOMPAH-691
  base_sha: 23d108b20c132b03c5dd450c1cb8ac97d4f0ffac
  updated_at: '2026-08-02T03:30:27.419803+00:00'
oompah.task_costs:
  total_input_tokens: 15
  total_output_tokens: 3362
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 15
      output_tokens: 3362
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 15
    output_tokens: 3362
    cost_usd: 0.0
    recorded_at: '2026-08-02T02:08:00.986705+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-693__20260802T020628Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: sonnet
    focus: duplicate_detector
    source_branch: epic-OOMPAH-691--task-OOMPAH-693
    source_sha: 6252b5434f392b74de9703a9fc8dca1951dfeaca
    completed_at: '2026-08-02T02:08:01.001135+00:00'
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
author: oompah
created: 2026-08-02 02:08
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 32, Tool calls: 22
- Tokens: 15 in / 3.4K out [3.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 44s
- Log: OOMPAH-693__20260802T020628Z.jsonl
---
author: oompah
created: 2026-08-02 03:30
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 03:30
---
Focus: Frontend Developer
---
author: oompah
created: 2026-08-02 03:30
---
UNDERSTANDING: This task requires implementing client-side dashboard resynchronization. Based on prior work (OOMPAH-692), the server has versioned WebSocket state, per-connection sequencing, and epoch reset semantics. As a frontend developer, I need to: (1) Add frontend logic to detect sequence/revision gaps, (2) Implement full-sync request handling via WebSocket, (3) Replace dashboard state atomically from the response while preserving revision watermarks, (4) Ensure accessibility and consistency with existing UI patterns. Starting code exploration now.
---
author: oompah
created: 2026-08-02 03:32
---
DISCOVERY: Reviewed OOMPAH-692 implementation. Server now has: (1) Versioned WebSocket protocol v1 with envelope fields (protocol_version, epoch, delivery_seq, state_revision, issue_revision), (2) Per-connection delivery sequences to detect transport gaps, (3) Monotonic state/issue revisions within epochs, (4) Trailing-edge state coalescing. Planning document in plans/websocket-state-versioning.md clarifies protocol contract. Current refresh action sends state+issues. Next: Implement browser-side gap detection and full-sync request handling.
---
<!-- COMMENTS:END -->
