---
id: OOMPAH-694
type: feature
status: Open
priority: 1
title: Detect WebSocket gaps and self-heal the dashboard state
parent: OOMPAH-691
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-692
- OOMPAH-693
labels: []
assignee: null
created_at: '2026-08-02T02:01:50.443759Z'
updated_at: '2026-08-02T02:09:18.495561Z'
work_branch: epic-OOMPAH-691--task-OOMPAH-694
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: dc934fed7eecb194906f0886be10916d4912877d3877c51af4173b75cb8ad3bb
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 84a5cec2-f189-46e7-a921-dbcb9dd7cd66
  claim_owner: a99e28f1-69ee-4f52-9672-996f40b2018d
  claimed_at: '2026-08-02T02:09:01.128128+00:00'
  claim_expires_at: '2026-08-02T02:39:01.128128+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5df36bf6-6196-4985-ae7e-c580bfe9c363
oompah.work_branch: epic-OOMPAH-691--task-OOMPAH-694
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-691--task-OOMPAH-694
  base_branch: epic-OOMPAH-691
  base_sha: 6252b5434f392b74de9703a9fc8dca1951dfeaca
  updated_at: '2026-08-02T02:09:13.137005+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 02:09
---
Duplicate screening dispatched (profile: standard, task remains Open)
---
author: oompah
created: 2026-08-02 02:09
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
