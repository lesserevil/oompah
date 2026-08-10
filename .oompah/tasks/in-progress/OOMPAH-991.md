---
id: OOMPAH-991
type: bug
status: In Progress
priority: 1
title: Isolate WebSocket bootstrap tests from process-global state snapshots
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:30:40.633471Z'
updated_at: '2026-08-10T10:31:38.179561Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-989

PR 798 exposed an order-dependent CI failure in test_ws_bootstrap_structure_preserved. OOMPAH-989 restart tests leave partial process-global server state snapshots, while the WebSocket _ws_isolation helper resets clients and orchestrator but not the snapshot/protocol cache, so xdist worker order controls the bootstrap payload. Scope: exactly save, clear, and restore all state cache authority/revision globals in the WebSocket helper and every restart regression that mutates them; add poison-cache and sentinel-restore regressions; preserve production partial-cache and fail-closed semantics. Run affected WebSocket, restart, and server tests with the deterministic leaking-test-then-victim order, repeated xdist stress, and the full Makefile gate. Acceptance: Python 3.11/3.12/3.13 CI is independent of worker assignment, cache globals are restored exactly, and no stale data or credentials are exposed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

