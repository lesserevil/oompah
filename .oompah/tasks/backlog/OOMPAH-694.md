---
id: OOMPAH-694
type: feature
status: Backlog
priority: 1
title: Detect WebSocket gaps and self-heal the dashboard state
parent: OOMPAH-691
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-692
- OOMPAH-693
labels:
- needs:frontend
assignee: null
created_at: '2026-08-02T02:01:50.443759Z'
updated_at: '2026-08-02T02:02:37.588981Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Implement the browser-side convergence state machine using the server epoch, delivery sequence, authoritative revisions, heartbeat watermarks, and full-sync operation.

Scope:
- Track the active service epoch, last contiguous delivery sequence, and last applied state/issue revisions.
- Detect delivery gaps, sequence regression, epoch changes, and pong/current-watermark values newer than the applied UI state.
- On detection, mark synchronization as stale/reconciling, issue exactly one full-sync request, and suppress duplicate requests while it is in flight.
- Buffer or discard incremental messages safely during resync; atomically apply the full state/issues response; reset reconciliation markers; then resume only from messages newer than the returned watermark.
- Use bounded retry/backoff after full-sync failure and keep the operator-visible connection status truthful.
- Preserve open detail panels, inline edits, drag state, filters, console transcript behavior, and incremental board DOM reconciliation.

Relevant files: oompah/templates/dashboard.html WebSocket handlers and render state, tests/test_dashboard_websocket_liveness.py, tests/test_dashboard_board_reconciliation.py, tests/test_console_ui.py, and related UI source-contract tests.

Required tests:
- Contiguous messages do not request a full sync.
- A skipped sequence or newer heartbeat watermark triggers one request.
- Repeated gap signals while resync is active do not create a request storm.
- Epoch change clears old ordering state and applies a fresh snapshot.
- Out-of-order buffered messages cannot overwrite the full-sync watermark.
- Auditor completion removes stale running-agent chips after a simulated dropped completion message.
- UI-local editing, drag, filter, and console state survive recovery.

Acceptance criteria:
- A live but out-of-date dashboard converges automatically within a bounded heartbeat/resync interval.
- The operator never has to reload the page to clear stale agent chips, alerts, counters, or task columns.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

