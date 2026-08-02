---
id: OOMPAH-691
type: epic
status: Needs CI Fix
priority: 0
title: Make dashboard WebSocket state provably convergent
parent: null
children:
- OOMPAH-692
- OOMPAH-693
- OOMPAH-694
- OOMPAH-695
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-02T02:00:17.265294Z'
updated_at: '2026-08-02T07:15:53.877036Z'
work_branch: epic-OOMPAH-691
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/654
review_number: '654'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/654
oompah.review_number: '654'
oompah.work_branch: epic-OOMPAH-691
oompah.target_branch: main
oompah.agent_run_id: 48308078-3dd3-40cc-b41b-72ca94d9324d
---
## Summary

Triggered by: OOMPAH-690

The dashboard currently consumes best-effort WebSocket snapshots without a durable ordering or freshness contract. A throttled or transport-lost state update can leave lastRunningAgents, alerts, task state, or other rendered data stale while the socket remains healthy and heartbeat pongs continue. Define and ship a versioned synchronization protocol that lets the browser prove whether its state is current and request an authoritative full replacement when it is not.

Scope:
- Add a per-service stream epoch and monotonic sequence/revision semantics that cover authoritative state changes, including changes coalesced before broadcast.
- Expose the latest revision in normal WebSocket envelopes and heartbeat responses so a live connection can still reveal that the browser is behind.
- Add a coherent full-state resynchronization response containing state, issues, and the revision watermark used to build them.
- Make the dashboard detect gaps, epoch changes, and stale revision watermarks; request one guarded full resync and atomically replace affected client state.
- Preserve console events, authenticated ws/wss behavior, incremental board rendering, editing/drag state, and reconnect backfill.
- Add operator-visible metrics/tests proving detection, recovery, and bounded request behavior under dropped, reordered, throttled, and reconnect scenarios.

Relevant code: oompah/server.py WebSocket broadcast/cache lifecycle, oompah/orchestrator.py observer notifications, oompah/templates/dashboard.html connection and state handlers, and WebSocket/dashboard lifecycle tests.

Acceptance criteria:
- Every authoritative dashboard state mutation advances a monotonic revision within a service epoch even when its immediate broadcast is coalesced.
- A connected browser can detect that it missed one or more mutations without relying on a manual refresh or socket failure.
- Gap detection triggers exactly one bounded full-state request, applies a coherent replacement, and resumes incremental processing from the returned watermark.
- Agent chips, alerts, task columns, and counters converge to the server state after dropped/coalesced messages.
- Focused race/lifecycle tests and the complete Makefile test gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 07:01
---
Branch quality gate passed for `1edd55f7c62f43448dd1d485e069cf3b61efd25b` using `make test` in 390.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-02 07:09
---
YOLO: CI tests failed on MR #654. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-08-02 07:10
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-02 07:10
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-02 07:11
---
Understanding: CI failed only on Python 3.12 and 3.13 (3.11 passed) on the same test: \`tests/test_ws_lifecycle.py::TestWebSocketRefreshAction::test_refresh_action_sends_state_back\` — pytest-timeout at 5s while receiving the 3rd message after sending {action: refresh}. This is a WS lifecycle test in the epic's convergence work. Plan: reproduce locally, inspect refresh handler on the server, and either loosen the read loop or ensure the refresh reliably drives the expected number of messages within the timeout.
---
<!-- COMMENTS:END -->
