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
updated_at: '2026-08-10T10:37:47.307104Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 10:37
---
Test-isolation blocker fix is committed and pushed at exact head f2a3a397273c5d6f051ff6754b715bb4e64e2b8d on branch OOMPAH-989. Restart API tests now save and restore the complete server snapshot/protocol tuple under the snapshot then protocol locks. WebSocket isolation atomically clears that tuple to coherent unavailable defaults and restores the exact prior snapshot, timestamp, epoch, authority, signature, protocol epoch, state revision, and issue revision. Poison-cache and exact sentinel restoration regressions were added; production normalization was not changed. Evidence: original leaking-test then victim order passed 2/2 serial and 2/2 with xdist n=1; both new regressions passed 2/2; both affected files passed 44/44; all three known restart leakers followed by the victim passed 10/10 repeated xdist n=1 runs; compileall and git diff --check passed. No new full gate was run because this is the narrow PR 798 blocker requested for the already-gated OOMPAH-989 integration head. OOMPAH-991 remains In Progress for owner disposition.
---
<!-- COMMENTS:END -->
