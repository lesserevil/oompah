---
id: OOMPAH-694
type: feature
status: In Progress
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
updated_at: '2026-08-02T04:06:32.147062Z'
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
  verdict: no_duplicate
  checked_at: '2026-08-02T02:10:27.690885+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: Searched all native task states plus docs/plans for\
    \ WebSocket, full-sync, delivery-sequence, heartbeat, reconciliation, and stale-dashboard\
    \ terms. The closest task, OOMPAH-205, is Archived and only implemented incremental\
    \ DOM reconciliation for unchanged issue snapshots\u2014not protocol ordering,\
    \ epochs, watermarks, or recovery. OOMPAH-216 is also Archived and concerns Release\
    \ Delivery reconciliation. The only active stored tasks are unrelated."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4fddde2c-4359-4a0a-86fb-e025bb3cb89b
oompah.work_branch: epic-OOMPAH-691--task-OOMPAH-694
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-691--task-OOMPAH-694
  base_branch: epic-OOMPAH-691
  base_sha: cf5f3cecede5a3344922345e2fcbc3f042c982c9
  updated_at: '2026-08-02T04:06:29.653932+00:00'
oompah.task_costs:
  total_input_tokens: 415198
  total_output_tokens: 2198
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 415198
      output_tokens: 2198
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 415198
    output_tokens: 2198
    cost_usd: 0.0
    recorded_at: '2026-08-02T02:10:27.689432+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-694__20260802T020920Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: duplicate_detector
    source_branch: epic-OOMPAH-691--task-OOMPAH-694
    source_sha: 6252b5434f392b74de9703a9fc8dca1951dfeaca
    completed_at: '2026-08-02T02:10:27.762886+00:00'
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
author: oompah
created: 2026-08-02 02:10
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 8
- Tokens: 415.2K in / 2.2K out [417.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 20s
- Log: OOMPAH-694__20260802T020920Z.jsonl
---
author: oompah
created: 2026-08-02 04:06
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 04:06
---
Focus: Frontend Developer
---
<!-- COMMENTS:END -->
