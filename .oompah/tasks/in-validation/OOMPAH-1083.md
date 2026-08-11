---
id: OOMPAH-1083
type: task
status: In Validation
priority: null
title: Publish quality-gate lifecycle state before stale PID alerts escape
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T11:41:11.895675Z'
updated_at: '2026-08-11T13:12:30.509415Z'
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
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-70da08ae8588
    project_id: proj-14849f1b
    task_id: OOMPAH-1083
    digest: d45dbe7ec74b541ada3f91bb32e0540ea540db011e45564e57d3ddee219dfe57
  - version: 1
    audit_id: audit-c104759340b1
    project_id: proj-14849f1b
    task_id: OOMPAH-1083
    digest: d45dbe7ec74b541ada3f91bb32e0540ea540db011e45564e57d3ddee219dfe57
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1083","audit-70da08ae8588","attempt-5f050ef39385"]': '2026-08-11T13:12:21.540557+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1083
    target_state: Done
    evidence_fingerprint: d45dbe7ec74b541ada3f91bb32e0540ea540db011e45564e57d3ddee219dfe57
    workflow_revision: null
    selected_ref: be48003555fed724a752512d73fd70d5c72b2795
    selected_sha: be48003555fed724a752512d73fd70d5c72b2795
    landing_revision: null
    audit_ids:
    - audit-70da08ae8588
    kind: result
    applied: true
    retired_at: '2026-08-11T13:12:21.540573+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1083
    audit_id: audit-70da08ae8588
    attempt_id: attempt-5f050ef39385
    target_state: Done
    evidence_fingerprint: d45dbe7ec74b541ada3f91bb32e0540ea540db011e45564e57d3ddee219dfe57
    status: In Validation
    audit_ids:
    - audit-70da08ae8588
    kind: result
    applied: true
    created_at: '2026-08-11T13:12:21.540584+00:00'
    applied_at: '2026-08-11T13:12:28.772065+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-70da08ae8588
    project_id: proj-14849f1b
    task_id: OOMPAH-1083
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d45dbe7ec74b541ada3f91bb32e0540ea540db011e45564e57d3ddee219dfe57
    attempts:
    - version: 1
      attempt_id: attempt-5f050ef39385
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d45dbe7ec74b541ada3f91bb32e0540ea540db011e45564e57d3ddee219dfe57
      created_at: '2026-08-11T13:09:51.241454+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T13:09:51.241454+00:00'
      branch_key: OOMPAH-1083
      selected_ref: be48003555fed724a752512d73fd70d5c72b2795
      selected_sha: be48003555fed724a752512d73fd70d5c72b2795
      verdict: pass
      completed_at: '2026-08-11T13:12:21.540406+00:00'
      ended_at: '2026-08-11T13:12:21.540406+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T13:06:04.676643+00:00'
    eligible_at: '2026-08-11T13:06:04.676643+00:00'
    selected_ref: be48003555fed724a752512d73fd70d5c72b2795
    selected_sha: be48003555fed724a752512d73fd70d5c72b2795
    updated_at: '2026-08-11T13:12:21.540406+00:00'
  - version: 1
    audit_id: audit-c104759340b1
    project_id: proj-14849f1b
    task_id: OOMPAH-1083
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d45dbe7ec74b541ada3f91bb32e0540ea540db011e45564e57d3ddee219dfe57
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T13:06:04.676643+00:00'
    prerequisite_audit_id: audit-70da08ae8588
    selected_ref: be48003555fed724a752512d73fd70d5c72b2795
    selected_sha: be48003555fed724a752512d73fd70d5c72b2795
    updated_at: '2026-08-11T13:12:21.540406+00:00'
    eligible_at: '2026-08-11T13:12:21.540406+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5f050ef39385
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d45dbe7ec74b541ada3f91bb32e0540ea540db011e45564e57d3ddee219dfe57
    created_at: '2026-08-11T13:09:51.241454+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T13:09:51.241454+00:00'
    branch_key: OOMPAH-1083
    selected_ref: be48003555fed724a752512d73fd70d5c72b2795
    selected_sha: be48003555fed724a752512d73fd70d5c72b2795
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
author: oompah
created: 2026-08-11 12:55
---
Protected CI Python 3.12 passed all 19,945 test bodies but hit a load-sensitive autouse teardown timeout while closing TransitionJournal; 3.11 and 3.13 are green. Exact-head Python 3.12 focused test passed 10/10 locally, independent diagnosis found no OOMPAH-1083 regression, and only the failed 3.12 matrix cell is rerunning as job 93785370387. Filed and directly claimed OOMPAH-1086 to make the observed cleanup boundary deterministic rather than hiding the race.
---
author: oompah
created: 2026-08-11 12:58
---
Independent exact-head adversarial review ACCEPTED be48003555fed724a752512d73fd70d5c72b2795 after the prior bf823 authority was revoked. Reviewer verified the focused lifecycle/PID-reuse cases (17), alert/IPC slice (56), and all 21 terminal-mutation scan entries. Current main composition was also verified clean with 29 combined tests; merge remains gated only on the protected Python 3.12 rerun.
---
author: oompah
created: 2026-08-11 13:06
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 13:09
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 13:10
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 13:12
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- gate_status: passed
- duration_seconds: 175.97
- lifecycle_publication: implemented
- stale_snapshot_sanitization: implemented
- pid_reuse_fencing: implemented
- callback_isolation: implemented
- concurrent_owners: verified
- independent_review: accepted
- py312_status: timeout-unrelated-1086
---
<!-- COMMENTS:END -->
