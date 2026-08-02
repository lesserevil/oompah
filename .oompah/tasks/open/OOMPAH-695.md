---
id: OOMPAH-695
type: task
status: Open
priority: 1
title: Prove dashboard convergence with fault injection and health telemetry
parent: OOMPAH-691
children: []
blocked_by:
- OOMPAH-692
- OOMPAH-693
- OOMPAH-694
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T02:01:52.297786Z'
updated_at: '2026-08-02T02:13:15.184171Z'
work_branch: epic-OOMPAH-691--task-OOMPAH-695
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 97f4db1bf286d42457f4567f6663e2eb196a86fc78c5a548f792455e31e54d93
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: a1e42402-38f2-4156-a284-eda7093e62c3
  claim_owner: a99e28f1-69ee-4f52-9672-996f40b2018d
  claimed_at: '2026-08-02T02:10:33.887440+00:00'
  claim_expires_at: '2026-08-02T02:40:33.887440+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 854f0926-b90b-4e4c-a141-114da4d89430
oompah.work_branch: epic-OOMPAH-691--task-OOMPAH-695
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-691--task-OOMPAH-695
  base_branch: epic-OOMPAH-691
  base_sha: 6252b5434f392b74de9703a9fc8dca1951dfeaca
  updated_at: '2026-08-02T02:10:41.847108+00:00'
---
## Summary

Add end-to-end regression coverage and operator diagnostics for the sequenced WebSocket recovery protocol.

Scope:
- Build a deterministic WebSocket/browser test harness that can drop, duplicate, delay, and reorder selected state/issues messages while keeping the connection open and answering heartbeats.
- Cover the observed failure: four auditors finish, their completion snapshots are coalesced or dropped, the browser detects its older revision, requests full sync, and removes all four chips without reload.
- Exercise disconnect/reconnect, service epoch replacement, concurrent issue/state changes, full-sync construction races, and resync failure/retry.
- Add bounded counters/timestamps for gaps detected, full-sync requests, successes, failures, and last successful reconciliation. Expose them through existing safe state/metrics surfaces without alerting on normal recovered gaps.
- Define an alert only for repeated or stale unrecovered synchronization failure, with actionable remediation and deduplication.

Relevant files: WebSocket lifecycle and authenticated bootstrap tests, dashboard liveness/reconciliation tests, Granian end-to-end tests, oompah/server.py metrics/state payload, and operator-facing dashboard health rendering if needed.

Required tests:
- Fault-injected gaps converge to exact authoritative state.
- Duplicate/reordered messages cannot regress applied state.
- Resync requests remain bounded under a burst.
- Healthy recovery increments success metrics without producing an alert.
- Repeated unrecovered failures produce one actionable alert and clear after recovery.
- Complete make test gate passes on the exact review-ready head.

Acceptance criteria:
- Automated tests fail against the current lossy behavior and pass only when sequence detection and full synchronization work end to end.
- Operators can distinguish a healthy recovered gap from a stuck dashboard synchronization failure.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 02:10
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-02 02:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 02:13
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 44, Tool calls: 33
- Tokens: 20 in / 5.0K out [5.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 37s
- Log: OOMPAH-695__20260802T021051Z.jsonl
---
<!-- COMMENTS:END -->
