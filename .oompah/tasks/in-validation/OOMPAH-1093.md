---
id: OOMPAH-1093
type: bug
status: In Validation
priority: 2
title: '[backend:orchestrator] Orchestrator shutdown attempt failed; retaining process
  and retrying'
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T16:04:30.156611Z'
updated_at: '2026-08-11T17:51:28.516719Z'
work_branch: OOMPAH-1093
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/829
review_number: '829'
review_head: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1093
  base_branch: main
  base_sha: 3264da6780e35b10f759de8aade7b3509977bbb9
  head_sha: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
  submitted_at: '2026-08-11T16:42:50.783268+00:00'
  updated_at: '2026-08-11T16:54:34.019821+00:00'
oompah.work_branch: OOMPAH-1093
oompah.review_url: https://github.com/lesserevil/oompah/pull/829
oompah.review_number: '829'
oompah.target_branch: main
oompah.review_head: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-cab04fdebc43
    project_id: proj-14849f1b
    task_id: OOMPAH-1093
    digest: 7b902a87034bbeb8525abea1f341b4cbd1c8fbeb71b3cc8631931794b06af703
  - version: 1
    audit_id: audit-4715036950fd
    project_id: proj-14849f1b
    task_id: OOMPAH-1093
    digest: 7b902a87034bbeb8525abea1f341b4cbd1c8fbeb71b3cc8631931794b06af703
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1093","audit-cab04fdebc43","attempt-5cda2183be6b"]': '2026-08-11T17:36:20.656009+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1093
    target_state: Done
    evidence_fingerprint: 7b902a87034bbeb8525abea1f341b4cbd1c8fbeb71b3cc8631931794b06af703
    workflow_revision: null
    selected_ref: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
    selected_sha: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
    landing_revision: null
    audit_ids:
    - audit-cab04fdebc43
    kind: result
    applied: true
    retired_at: '2026-08-11T17:36:20.656024+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1093
    audit_id: audit-cab04fdebc43
    attempt_id: attempt-5cda2183be6b
    target_state: Done
    evidence_fingerprint: 7b902a87034bbeb8525abea1f341b4cbd1c8fbeb71b3cc8631931794b06af703
    status: In Validation
    audit_ids:
    - audit-cab04fdebc43
    kind: result
    applied: true
    created_at: '2026-08-11T17:36:20.656034+00:00'
    applied_at: '2026-08-11T17:36:28.486424+00:00'
  oompah.terminal_override_records:
  - version: 1
    override_id: override-21b3fa0c2cab
    project_id: proj-14849f1b
    task_id: OOMPAH-1093
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7b902a87034bbeb8525abea1f341b4cbd1c8fbeb71b3cc8631931794b06af703
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Operator audit under globally paused scheduling: independently accepted
      exact 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb; 144 focused restart, lifecycle,
      event and IPC checks passed; protected Python 3.11/3.12/3.13 CI passed; PR 829
      merged as 2d373679dece7b8b7fff5b67ff97c0e9648ac560; exact head is contained
      in current main.'
    created_at: '2026-08-11T17:51:26.691773+00:00'
    selected_ref: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
    selected_sha: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-cab04fdebc43
    project_id: proj-14849f1b
    task_id: OOMPAH-1093
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7b902a87034bbeb8525abea1f341b4cbd1c8fbeb71b3cc8631931794b06af703
    attempts:
    - version: 1
      attempt_id: attempt-5cda2183be6b
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 7b902a87034bbeb8525abea1f341b4cbd1c8fbeb71b3cc8631931794b06af703
      created_at: '2026-08-11T17:26:27.879035+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-11T17:26:27.879035+00:00'
      branch_key: OOMPAH-1093
      selected_ref: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
      selected_sha: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
      verdict: pass
      completed_at: '2026-08-11T17:36:20.655853+00:00'
      ended_at: '2026-08-11T17:36:20.655853+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T17:21:51.663675+00:00'
    eligible_at: '2026-08-11T17:21:51.663675+00:00'
    selected_ref: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
    selected_sha: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
    updated_at: '2026-08-11T17:36:20.655853+00:00'
  - version: 1
    audit_id: audit-4715036950fd
    project_id: proj-14849f1b
    task_id: OOMPAH-1093
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7b902a87034bbeb8525abea1f341b4cbd1c8fbeb71b3cc8631931794b06af703
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-11T17:21:51.663675+00:00'
    prerequisite_audit_id: audit-cab04fdebc43
    selected_ref: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
    selected_sha: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
    updated_at: '2026-08-11T17:36:20.655853+00:00'
    eligible_at: '2026-08-11T17:36:20.655853+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5cda2183be6b
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7b902a87034bbeb8525abea1f341b4cbd1c8fbeb71b3cc8631931794b06af703
    created_at: '2026-08-11T17:26:27.879035+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-11T17:26:27.879035+00:00'
    branch_key: OOMPAH-1093
    selected_ref: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
    selected_sha: 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 294
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 10
      output_tokens: 294
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 10
    output_tokens: 294
    cost_usd: 0.0
    recorded_at: '2026-08-11T17:36:46.619009+00:00'
---
## Summary

### Problem
Oompah detected a backend error from `backend:orchestrator`:

> Orchestrator shutdown attempt failed; retaining process and retrying

### Steps to Reproduce
1. Run oompah with `backend:orchestrator` active.
2. Let oompah operate on the `proj-14849f1b` project (tracker: `provenanceguardedtracker`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior
An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Orchestrator shutdown attempt failed; retaining process and retrying

### Expected Behavior
The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Acceptance Criteria
- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: proj-14849f1b
- tracker: provenanceguardedtracker
- tracker_kind: provenanceguardedtracker
- fingerprint: 9984037ce1db983d
- dedup_fingerprint: 9984037ce1db983d

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 16:09
---
Live reproduction during normal make restart at 2026-08-11T16:04Z: shutdown quiesced while a terminal auditor was between durable claim/worktree preparation and provider admission. Orchestrator._drain_background_work raised RuntimeError('lifecycle publication snapshot did not drain; refusing to close lifecycle stores'); stop_until_safe retained the process and its next attempt succeeded, then os.execv completed. The interrupted auditor lease recovered as abandoned/retry_wait. Repair scope: make the graceful shutdown publication drain converge deterministically when terminal-audit/provider admission loses the quiesce race, without reporting a backend error for a safely retryable internal drain; retain fail-closed refusal to close stores while true writers remain. Add a deterministic barrier regression around audit claim/provider-admission versus quiesce, prove bounded retry reaches a fully published snapshot and clean shutdown with no orphan workflow lease/attempt/worktree, and preserve error reporting when progress is genuinely impossible.
---
author: oompah
created: 2026-08-11 16:16
---
Implemented and pushed exact head 8031e7f74b6836ec0480fb3065961995fbfa28a8 (based current main 3264da678). Added LifecyclePublicationDrainPending so direct background drain remains fail-closed, while stop() classifies an already-revoked snapshot worker's bounded join timeout as safely retained authority and returns False for stop_until_safe's retry instead of logging an error. Deterministic regression blocks a real lifecycle snapshot beyond the join timeout, proves stores remain open, no 'shutdown attempt failed' error is emitted, then release causes bounded retry, clean store close, and completed shutdown. Checks: 33 restart API tests + 110 event-loop/resource/granian tests passed; terminal mutation scan 21/21; diff/secret hooks clean. Awaiting independent exact-head review; not submitted.
---
author: oompah
created: 2026-08-11 16:24
---
Normalized the commit message to the required canonical attribution trailer without changing the patch and force-pushed with an exact lease. Current review candidate is 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb; diff versus prior 8031e7f74b6836ec0480fb3065961995fbfa28a8 is commit metadata only. Existing verification remains valid: 33 restart API tests, 110 adjacent lifecycle/resource tests, terminal mutation scan 21/21, clean diff and secret hooks. Awaiting independent review; not submitted.
---
author: oompah
created: 2026-08-11 16:33
---
Fresh independent review ACCEPTED exact head 4c6de3f056fcec98fa1e0118e7fe683c76b71ceb. Reviewer verified only LifecyclePublicationDrainPending is normalized to a bounded stop retry; lifecycle callback/snapshot authority prevents store teardown; direct drain and unrelated exceptions remain fail-closed; no observer recursion or false backend-error alert occurs; and the retry converges after authority exits. Independent evidence: 33 restart API tests, 111 supporting lifecycle/event/IPC tests and negative-path probes, clean diff. Holding submission only until the current OOMPAH-1085 canonical gate has the sole validation slot; not merged.
---
author: oompah
created: 2026-08-11 16:43
---
Treat retained lifecycle-publication drain authority as a bounded graceful-stop retry while keeping stores open and unrelated failures fail-closed.
---
author: oompah
created: 2026-08-11 16:52
---
Branch quality gate passed for `4c6de3f056fcec98fa1e0118e7fe683c76b71ceb` using `make test` in 180.2s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 17:07
---
Branch quality gate passed for `4c6de3f056fcec98fa1e0118e7fe683c76b71ceb` using `make test` in 180.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-11 17:21
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-11 17:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-11 17:26
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-11 17:36
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- patch_scope: LifecyclePublicationDrainPending exception class + exception handling in stop()/stop_until_safe()
- exception_hierarchy: LifecyclePublicationDrainPending(RuntimeError) - allows compatibility with existing exception handling
- fail_closed_retained: Stores remain open while drain pending; only this exception class is safe-retryable; other exceptions still log error
- regression_test: test_safe_stop_retries_retired_snapshot_without_backend_error verifies no error logged for lifecycle drain timeout, stores remain open until release
- authoritative_evidence: make test: 180.1s passed, 33 restart API + 110+ lifecycle/event tests, terminal mutation 21/21, clean diff/hooks
- root_cause_addressed: Terminal auditor claim/worktree admission no longer loses quiesce race; publication drain timeout classified as bounded graceful-stop retry, not backend error
---
author: oompah
created: 2026-08-11 17:36
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 106, Tool calls: 49
- Tokens: 10 in / 294 out [304 total]
- Cost: $0.0000
- Exit: normal, Duration: 10m 12s
- Log: OOMPAH-1093__20260811T172658Z.jsonl
---
<!-- COMMENTS:END -->
