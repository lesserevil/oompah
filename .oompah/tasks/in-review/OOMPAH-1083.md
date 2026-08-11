---
id: OOMPAH-1083
type: task
status: In Review
priority: null
title: Publish quality-gate lifecycle state before stale PID alerts escape
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T11:41:11.895675Z'
updated_at: '2026-08-11T12:30:17.541028Z'
work_branch: OOMPAH-1083
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/820
review_number: '820'
review_head: be48003555fed724a752512d73fd70d5c72b2795
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: 5df42b13-d647-40d8-bf16-ea593024a893
  request_fingerprint: 875facd4bb649c5339eb1993dd3053f79d20a2988f2f3839d2fd52d61ce85c19
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1083
  base_branch: main
  base_sha: 712309b8179036474e40c5fd26f7d2b3c2a4b9b0
  head_sha: be48003555fed724a752512d73fd70d5c72b2795
  submitted_at: '2026-08-11T12:24:29.350965+00:00'
  updated_at: '2026-08-11T12:24:29.350965+00:00'
oompah.work_branch: OOMPAH-1083
oompah.review_url: https://github.com/lesserevil/oompah/pull/820
oompah.review_number: '820'
oompah.target_branch: main
oompah.review_head: be48003555fed724a752512d73fd70d5c72b2795
---
## Summary

Triggered by live OOMPAH-1080/OOMPAH-1082 integration evidence on 2026-08-11. The exact BranchQualityGate owner registry remained correct, but /api/v1/state served a cached snapshot for more than two minutes after gate A exited and gate B started; state_snapshot_stale=true while the UI continued asserting gate A's dead PID/task as actively running. Scope: emit a non-blocking, coalesced state-only/lifecycle publication on exact quality-gate process registration and final removal across pass, failure, timeout, cancellation, and exception paths, outside the BranchQualityGate process lock; callback/publication failure must never alter gate outcomes. Add defense-in-depth so stale snapshots do not present PID-backed quality-gate alerts as current (label them stale or suppress task-specific running assertions) without recomputing heavy orchestrator state in the API. Relevant code: oompah/quality_gate.py, orchestrator state publication, server cached-state/alert projection, HTTP and WebSocket snapshot publication tests. Required tests: block the scheduler tick while gate A exits and gate B starts and prove cached HTTP plus WS state advances to exact gate B; all terminal gate paths remove dead PIDs and publish; concurrent gates retain other owners; callback executes outside the process lock without deadlock; callback failure is isolated; API-only/IPC parity, snapshot sequence advancement, and no duplicate task-specific alerts. Acceptance: within one bounded publication interval after gate lifecycle change, the UI cannot continue showing a dead gate PID/task as actively running even when the full scheduler reconciliation is blocked; focused tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 12:03
---
Published exact quality-gate registration/removal edges through non-blocking coalesced lifecycle state, retained same-generation updates missed by in-flight snapshots, and suppressed stale PID-backed running assertions across REST/IPC/WebSocket views. Covered pass, failure, timeout, cancellation, runner/callback exceptions, concurrent owners, A-to-B replacement revision advancement, alert deduplication, and IPC parity.
---
author: oompah
created: 2026-08-11 12:08
---
Branch quality gate passed for `bf823293fc6dc2417a0438a9ead7c54c84732163` using `make test` in 173.6s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 12:09
---
Independent exact-head review BLOCKED bf823293fc6dc2417a0438a9ead7c54c84732163. Production-shaped IPC repro aged kv.updated_at by 60s; api_state discarded updated_at, no stale marker was derived, and dead PID/running gate assertions remained. Explicit stale sanitization also left top-level/health quality_gates.status=running. A numeric-PID-only cleanup path can remove/signal a replacement registration after PID reuse. Author is fixing authoritative IPC-age derivation, complete stale running-state reconciliation, and exact registration/process identity CAS with regressions; this head will not merge.
---
author: oompah
created: 2026-08-11 12:24
---
Publish exact quality-gate lifecycle state and sanitize aged IPC projections at be48003555fed724a752512d73fd70d5c72b2795; exact process/token PID-reuse fencing, 394 focused and 46 adjacent tests, mutation and secret scans pass.
---
author: oompah
created: 2026-08-11 12:29
---
Branch quality gate passed for `be48003555fed724a752512d73fd70d5c72b2795` using `make test` in 176.0s. Review creation may proceed.
---
<!-- COMMENTS:END -->
