---
id: OOMPAH-695
type: task
status: Backlog
priority: 1
title: Prove dashboard convergence with fault injection and health telemetry
parent: OOMPAH-691
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T02:01:52.297786Z'
updated_at: '2026-08-02T02:01:52.297786Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

