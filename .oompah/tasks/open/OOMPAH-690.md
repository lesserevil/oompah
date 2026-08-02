---
id: OOMPAH-690
type: task
status: Open
priority: null
title: Restore reliable automatic dashboard updates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T00:37:18.141681Z'
updated_at: '2026-08-02T00:39:03.709373Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 4448eb9e9bf16ed805655767845203a2dd0fe95eded17aba4e22100a9a603172
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 71f15830-8dd8-4a5e-844e-bba46a828290
  claim_owner: 9c8dda42-c87b-429a-bdb1-42da8ebebe7e
  claimed_at: '2026-08-02T00:39:02.707027+00:00'
  claim_expires_at: '2026-08-02T01:09:02.707027+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

The live dashboard remains WebSocket-connected but task and alert changes can require a browser refresh before appearing. A concrete server loss path exists in oompah.server._on_orchestrator_change: state-only agent activity and issue-changing notifications share _last_state_broadcast. If activity updates the timestamp less than 500 ms before a task transition, _on_orchestrator_change returns before scheduling _throttled_broadcast_issues, permanently dropping that board refresh. The browser also sends no heartbeat, so a silently severed proxy connection can remain apparently Connected without forcing reconnect/backfill.

Implementation scope:
- Ensure every issue-changing orchestrator notification schedules a throttled/debounced issues refresh even when its state message is suppressed by the state throttle.
- Keep state-message throttling independent from issue refresh scheduling and retain coalescing under rapid event bursts.
- Add browser WebSocket liveness handling with a bounded heartbeat or refresh probe, pong/data freshness tracking, stale connection closure, reconnect backoff, and immediate state/issues backfill after reconnect.
- Prevent overlapping reconnect timers and duplicate sockets; clean timers on close/reconnect/page teardown.
- Surface Reconnecting or stale status rather than leaving Connected on a non-delivering socket.
- Preserve authenticated ws/wss URL behavior and console transcript backfill.

Relevant code: oompah/server.py observer and WebSocket broadcast functions, oompah/templates/dashboard.html connectWebSocket, and dashboard/WebSocket lifecycle tests.

Required tests:
- A state-only notification immediately followed within the throttle window by an issue-changing notification still schedules exactly one issues broadcast containing the fresh board snapshot.
- Rapid issue changes are coalesced without being lost.
- Browser heartbeat detects a non-responsive connection, closes it, reconnects once, and requests/backfills current state and issues.
- Normal inbound traffic keeps the connection alive; explicit close/error paths do not create duplicate reconnects.
- Existing authenticated WebSocket bootstrap, console reconnect, and Granian fan-out tests remain green.

Acceptance criteria:
- Task status, agent assignment, Needs Human, and alert-related board changes appear without browser reload.
- No issue-changing notification can be dropped solely because a state-only message was recently broadcast.
- A dead connection self-recovers within a bounded interval and visibly reports reconnecting state.
- Focused dashboard/WebSocket tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 00:37
---
Operator claimed this live dashboard-refresh regression for direct implementation.
---
<!-- COMMENTS:END -->
