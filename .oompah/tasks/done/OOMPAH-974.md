---
id: OOMPAH-974
type: bug
status: Done
priority: 1
title: Keep lifecycle control recoverable when workflow reconciliation deadlocks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T21:05:01.679955Z'
updated_at: '2026-08-09T22:13:09.427712Z'
work_branch: OOMPAH-974
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/783
review_number: '783'
review_head: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-974
  head_sha: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
  submitted_at: '2026-08-09T21:50:33.423286+00:00'
  updated_at: '2026-08-09T21:50:33.423286+00:00'
oompah.work_branch: OOMPAH-974
oompah.review_url: https://github.com/lesserevil/oompah/pull/783
oompah.review_number: '783'
oompah.target_branch: main
oompah.review_head: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-d565b6a25f30
    project_id: proj-14849f1b
    task_id: OOMPAH-974
    digest: b7b99d84dbacb4f7eeeea41f8bda2788f0e20ee20d31a0dd6a2f3c24190e4660
  - version: 1
    audit_id: audit-e005f71194c1
    project_id: proj-14849f1b
    task_id: OOMPAH-974
    digest: b7b99d84dbacb4f7eeeea41f8bda2788f0e20ee20d31a0dd6a2f3c24190e4660
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-974","audit-d565b6a25f30","attempt-64bedb0842a2"]': '2026-08-09T22:11:47.822345+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-974
    target_state: Done
    evidence_fingerprint: b7b99d84dbacb4f7eeeea41f8bda2788f0e20ee20d31a0dd6a2f3c24190e4660
    audit_ids:
    - audit-d565b6a25f30
    - audit-e005f71194c1
    kind: override
    applied: true
    retired_at: '2026-08-09T22:11:47.822373+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-974
    audit_id: audit-d565b6a25f30
    attempt_id: attempt-64bedb0842a2
    target_state: Done
    evidence_fingerprint: b7b99d84dbacb4f7eeeea41f8bda2788f0e20ee20d31a0dd6a2f3c24190e4660
    status: In Validation
    audit_ids:
    - audit-d565b6a25f30
    kind: result
    applied: true
    created_at: '2026-08-09T22:11:47.822392+00:00'
    applied_at: '2026-08-09T22:12:00.936224+00:00'
    retired_by_override: true
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6593d203adb9
    project_id: proj-14849f1b
    task_id: OOMPAH-974
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7b99d84dbacb4f7eeeea41f8bda2788f0e20ee20d31a0dd6a2f3c24190e4660
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Protected PR #783 merged exact head 8526a01b into 9ea2d4d07; Python 3.11/3.12/3.13
      gates passed, independent review approved with 399 tests, focused implementation
      suite passed 335, combined no-failure full run reached 8,580 tests, exact merge
      is deployed, force recovery succeeded, and health remained HTTP 200 throughout
      cold 1,776-task reconciliation. Auditor shell mutation attempts were policy-incompatible
      and add no authority beyond these exact checks.'
    created_at: '2026-08-09T22:12:28.374260+00:00'
    selected_ref: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
    selected_sha: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
    applied: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d565b6a25f30
    project_id: proj-14849f1b
    task_id: OOMPAH-974
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7b99d84dbacb4f7eeeea41f8bda2788f0e20ee20d31a0dd6a2f3c24190e4660
    attempts:
    - version: 1
      attempt_id: attempt-64bedb0842a2
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b7b99d84dbacb4f7eeeea41f8bda2788f0e20ee20d31a0dd6a2f3c24190e4660
      created_at: '2026-08-09T22:03:38.150577+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T22:03:38.150577+00:00'
      branch_key: OOMPAH-974
      selected_ref: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
      selected_sha: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
      verdict: pass
      completed_at: '2026-08-09T22:11:47.822065+00:00'
      ended_at: '2026-08-09T22:11:47.822065+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T21:59:24.029402+00:00'
    selected_ref: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
    selected_sha: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
    updated_at: '2026-08-09T22:11:47.822065+00:00'
  - version: 1
    audit_id: audit-e005f71194c1
    project_id: proj-14849f1b
    task_id: OOMPAH-974
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7b99d84dbacb4f7eeeea41f8bda2788f0e20ee20d31a0dd6a2f3c24190e4660
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T21:59:24.029402+00:00'
    selected_ref: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
    selected_sha: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
    updated_at: '2026-08-09T22:12:41.100637+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-64bedb0842a2
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b7b99d84dbacb4f7eeeea41f8bda2788f0e20ee20d31a0dd6a2f3c24190e4660
    created_at: '2026-08-09T22:03:38.150577+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T22:03:38.150577+00:00'
    branch_key: OOMPAH-974
    selected_ref: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
    selected_sha: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
oompah.task_costs:
  total_input_tokens: 330
  total_output_tokens: 11727
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 330
      output_tokens: 11727
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 330
    output_tokens: 11727
    cost_usd: 0.0
    recorded_at: '2026-08-09T22:12:56.158163+00:00'
---
## Summary

Triggered by: OOMPAH-737

Regression of OOMPAH-737/OOMPAH-350 observed live on 2026-08-09 while the 1,776-issue workflow reconciliation was active. The service kept PID 2715559 and port 8090 but /api/v1/state and /healthz returned no bytes; make graceful and make status timed out. After scheduler CPU stopped, the sole process remained indefinitely blocked in futex_do_wait. The documented emergency make force-restart also could not recover because canonical_cli_cutover required a responsive old /healthz, and identity-checked make stop sent SIGTERM but the process did not exit within 30 seconds. No worker child processes existed; recovery required verifying PID/cwd/process-group identity, SIGKILLing that exact service group, and make start. Implementation scope: reproduce a large/current workflow reconciliation that wedges scheduler/control-plane shutdown; identify and remove the remaining cross-thread/event-loop/GIL/deadlock path; keep /healthz, /api/v1/state, quiesce, restart-claim/cancel, and graceful/force lifecycle control responsive; and provide an identity-safe bounded emergency recovery when the old HTTP control plane is unresponsive. Preserve agent draining and never kill unverified processes. Relevant areas: scheduler thread isolation, workflow reconciliation/state publication, server shutdown, scripts/canonical_cli_cutover.py, Makefile lifecycle targets, and process identity. Required tests: blocked reconciliation cannot delay health/state/quiesce; graceful restart cuts over; emergency force-restart can recover a verified unresponsive old service without an HTTP precondition; SIGTERM shutdown is bounded; reused/wrong PID identity is refused; active-agent normal drain semantics remain intact. Acceptance: deterministic regressions pass, focused scheduler/restart/workflow suites and full gate pass, and a live large-corpus reconciliation remains controllable and restarts cleanly.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 21:05
---
Direct owner recovery/implementation claimed after live reproduction. Exact incident: verified service PID 2715559, no worker children, all HTTP lifecycle calls timed out, force-restart could not pass old-health precondition, SIGTERM stop exceeded 30 seconds, exact process group required SIGKILL, and make start recovered exact build 312c18ae3.
---
author: oompah
created: 2026-08-09 21:19
---
Additional post-restart liveness evidence: after generation 852 finished, SQLite had zero running jobs, but /api/v1/state continued to report workflow_runtime.worker active=3, retained=3, shared active lanes=3 and last admission repeatedly processed/scheduled zero. A priority-0 direct_owner_claim for OOMPAH-975 remained queued despite two explicit POST /api/v1/refresh requests. All worker/reconcile threads were sleeping; no new full tick published after 21:14:24. The fix must reconcile retained in-memory calls with terminal/exhausted durable rows and preserve the reserved control slot so priority-0 owner/lifecycle control cannot be starved by orphaned shared effects.
---
author: oompah
created: 2026-08-09 21:38
---
Implementation checkpoint: removed the large-corpus O(n^2) native detail-read amplification with a generation-scoped ID index and bounded cold-scan GIL yields; added cooperative pre-publication drain checkpoints across distinct implementation/review/integration/epic collectors; reserved direct_owner_claim in the control lane while preserving stale adapter calls until real settlement. Reworked make force-restart as a fully HTTP-independent exact-identity transaction: capture, stage/verify, bounded TERM then identity-rechecked SIGKILL, activate, then Make start. Wrong/stale PID remains refused. Focused new/reviewer regressions currently pass (14 tests); broader and full gates are next.
---
author: oompah
created: 2026-08-09 21:49
---
Implementation and review complete on exact base 312c18ae3. Validation: independent 399-test relevant suite passed; focused combined regression suite passed 335 tests; git diff --check and compileall passed (one unrelated pre-existing SyntaxWarning). A duplicate local make test run reached 8,580 passed, 7 skipped, 2 xfailed with no failures before all workers stalled in jbd2 filesystem journal waits; it was interrupted after 9m56s per operator direction because the protected exact-head gate runs once. Changes add indexed/cooperatively yielding native reads, drain-aware reconciliation checkpoints across all collector families, a reserved direct-owner control lane with retained-call safety, and identity-rechecked HTTP-independent emergency force restart escalation.
---
author: oompah
created: 2026-08-09 21:50
---
Implemented and pushed as 8526a01bfb741eb58c267e7f4b649b75f8bdc882. Native Markdown reads now use indexed cache lookup plus cooperative GIL checkpoints; workflow reconciliation is drain-aware across implementation, review, integration, and epic collectors; direct owner claims use the reserved control lane while stale non-cancellable effects remain retained; emergency force restart is HTTP-independent with exact process identity rechecks before bounded SIGKILL escalation. Validation: independent 399 relevant tests passed, focused combined suite 335 passed, diff check and compileall passed; duplicate full run reached 8,580 passed with no failures before operator-directed interruption during filesystem journal stalls.
---
author: oompah
created: 2026-08-09 21:54
---
Branch quality gate passed for `8526a01bfb741eb58c267e7f4b649b75f8bdc882` using `make test` in 160.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-09 21:59
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 22:03
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 22:03
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 22:04
---
Merged via protected PR #783 at 9ea2d4d07bfe2372b544989eaca47808e10e44c6 and deployed as exact service/CLI build. The old 312c process accepted restart but failed to settle; the newly merged HTTP-independent exact-identity force path boundedly quarantined it and started PID 2323184. Six consecutive health probes remained HTTP 200 throughout the cold 1,776-task initial reconciliation as state advanced from unavailable to live scan_complete=false snapshots. Independent review approved; 399 review tests, 335 focused tests, 8,580 additional no-failure full-gate tests, and protected Python 3.11/3.12/3.13 gates passed.
---
author: oompah
created: 2026-08-09 22:11
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- verified_head_sha: 8526a01bfb741eb58c267e7f4b649b75f8bdc882
- commit_message: OOMPAH-974: keep lifecycle control recoverable
- commit_trailer: Co-authored-by: oompah <lesserevil@users.noreply.github.com>
- quality_gate: make test passed in 160.71s on exact HEAD, result: passed
- implementation_scope: indexed read cache via _read_cache_by_id with cooperative GIL yields at 32-file intervals; cooperative checkpoints in _reconciliation_checkpoint; control_reserved_slots parameter; HTTP-independent force-restart in canonical_cli_cutover.py with --force flag; process identity verification via process_identity.py
- test_coverage: test_large_reconcile_cooperatively_releases_lifecycle_drain, test_each_domain_collector_cooperates_with_drain, test_force_restart_uses_transaction_without_agent_drain, test_force_restart_recovers_verified_service_without_http, test_emergency_quarantine_bounds_sigterm_and_escalates_exact_identity, test_quarantine_capture_refuses_stale_process_identity, test_runtime_owner_identity_fences_reused_pid_generation, test_graceful_drain_does_not_poison_active_shadow_qualification
- files_changed: 9 files, 815 net additions
---
author: oompah
created: 2026-08-09 22:12
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Protected PR #783 merged exact head 8526a01b into 9ea2d4d07; Python 3.11/3.12/3.13 gates passed, independent review approved with 399 tests, focused implementation suite passed 335, combined no-failure full run reached 8,580 tests, exact merge is deployed, force recovery succeeded, and health remained HTTP 200 throughout cold 1,776-task reconciliation. Auditor shell mutation attempts were policy-incompatible and add no authority beyond these exact checks.
---
author: oompah
created: 2026-08-09 22:13
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 86, Tool calls: 40
- Tokens: 330 in / 11.7K out [12.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 9m 15s
- Log: OOMPAH-974__20260809T220350Z.jsonl
---
author: oompah
created: 2026-08-09 22:13
---
Lifecycle/reconciliation recovery fix merged, deployed, and live-verified.
---
<!-- COMMENTS:END -->
