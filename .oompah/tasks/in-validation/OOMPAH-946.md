---
id: OOMPAH-946
type: task
status: In Validation
priority: 2
title: Remove detached native-validation descendant lifetime race
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:36:17.757446Z'
updated_at: '2026-08-09T13:58:35.890039Z'
work_branch: OOMPAH-946
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/758
review_number: '758'
review_head: 8e2527b74e958127861621fdbcebb627d0929e24
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-946
  head_sha: 8e2527b74e958127861621fdbcebb627d0929e24
  submitted_at: '2026-08-09T10:20:15.445451+00:00'
  updated_at: '2026-08-09T10:20:15.445451+00:00'
oompah.work_branch: OOMPAH-946
oompah.review_url: https://github.com/lesserevil/oompah/pull/758
oompah.review_number: '758'
oompah.target_branch: main
oompah.review_head: 8e2527b74e958127861621fdbcebb627d0929e24
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-1dbbda00b201
    project_id: proj-14849f1b
    task_id: OOMPAH-946
    digest: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
  - version: 1
    audit_id: audit-5b710ff06745
    project_id: proj-14849f1b
    task_id: OOMPAH-946
    digest: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-946","audit-1dbbda00b201","attempt-7f7dc8f82bbe"]': '2026-08-09T12:04:08.387247+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-946
    target_state: Done
    evidence_fingerprint: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
    audit_ids:
    - audit-1dbbda00b201
    kind: result
    applied: true
    retired_at: '2026-08-09T12:04:08.387263+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-946
    audit_id: audit-1dbbda00b201
    attempt_id: attempt-7f7dc8f82bbe
    target_state: Done
    evidence_fingerprint: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
    status: In Validation
    audit_ids:
    - audit-1dbbda00b201
    kind: result
    applied: true
    created_at: '2026-08-09T12:04:08.387272+00:00'
    applied_at: '2026-08-09T12:04:15.102109+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1dbbda00b201
    project_id: proj-14849f1b
    task_id: OOMPAH-946
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
    attempts:
    - version: 1
      attempt_id: attempt-7f7dc8f82bbe
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
      created_at: '2026-08-09T11:57:48.283643+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T11:57:48.283643+00:00'
      branch_key: OOMPAH-946
      selected_ref: 8e2527b74e958127861621fdbcebb627d0929e24
      selected_sha: 8e2527b74e958127861621fdbcebb627d0929e24
      verdict: pass
      completed_at: '2026-08-09T12:04:08.387121+00:00'
      ended_at: '2026-08-09T12:04:08.387121+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T11:17:43.998080+00:00'
    selected_ref: 8e2527b74e958127861621fdbcebb627d0929e24
    selected_sha: 8e2527b74e958127861621fdbcebb627d0929e24
    updated_at: '2026-08-09T12:04:08.387121+00:00'
  - version: 1
    audit_id: audit-5b710ff06745
    project_id: proj-14849f1b
    task_id: OOMPAH-946
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
    attempts:
    - version: 1
      attempt_id: attempt-566e3f0fa51e
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
      created_at: '2026-08-09T13:58:26.753314+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T13:58:26.753314+00:00'
      branch_key: OOMPAH-946
      selected_ref: 8e2527b74e958127861621fdbcebb627d0929e24
      selected_sha: 8e2527b74e958127861621fdbcebb627d0929e24
    source_generation: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T11:17:43.998080+00:00'
    selected_ref: 8e2527b74e958127861621fdbcebb627d0929e24
    selected_sha: 8e2527b74e958127861621fdbcebb627d0929e24
    updated_at: '2026-08-09T13:58:26.753314+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-7f7dc8f82bbe
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
    created_at: '2026-08-09T11:57:48.283643+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T11:57:48.283643+00:00'
    branch_key: OOMPAH-946
    selected_ref: 8e2527b74e958127861621fdbcebb627d0929e24
    selected_sha: 8e2527b74e958127861621fdbcebb627d0929e24
  - version: 1
    attempt_id: attempt-566e3f0fa51e
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 53e4358b2595ea287af1cea84cc565c182fedbced4063461c76633eb66431e07
    created_at: '2026-08-09T13:58:26.753314+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T13:58:26.753314+00:00'
    branch_key: OOMPAH-946
    selected_ref: 8e2527b74e958127861621fdbcebb627d0929e24
    selected_sha: 8e2527b74e958127861621fdbcebb627d0929e24
oompah.task_costs:
  total_input_tokens: 346
  total_output_tokens: 12307
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 346
      output_tokens: 12307
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 346
    output_tokens: 12307
    cost_usd: 0.0
    recorded_at: '2026-08-09T12:04:28.059551+00:00'
---
## Summary

Hosted CI run 31305502103 on reviewed OOMPAH-939 head b1fc26aa passed the complete Python 3.11 and 3.12 gates but failed Python 3.13 only in tests/test_native_validation_guard.py::test_detached_heavy_descendant_retains_native_capacity_until_exit: the wrapper-created detached descendant PID disappeared before the post-lease assertion. This test and its production lease watcher are the regression contract delivered by OOMPAH-841; no OOMPAH-939 code touches them. Scope: reproduce the Python 3.13/hosted-runner timing, determine whether the native wrapper/watch process prematurely terminates or the test observes before detached process readiness, and repair the production lifetime fence or deterministic test handshake as evidence requires. Do not relax the invariant that heavyweight descendants retain native capacity until their exact process generation exits, and do not replace PID/start-tick fencing with a sleep. Required tests: deterministic wrapper-exit/detached-child readiness handshake, descendant survives parent exit while lease remains held, PID reuse and genuine early-exit behavior, Python 3.11-3.13 focused matrix, terminal mutation/secret scans, and complete make test. Acceptance: repeated hosted matrix runs no longer fail this contract and exact lease capacity remains held for every live detached heavyweight descendant.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:20
---
Diagnosis confirmed from hosted run 31305502103 attempt 1: competing lease acquisition timed out even though /proc for the recorded PID vanished, so the production inherited-descriptor fence remained held. The test recorded the transient setsid launcher via $!, which may fork when it is already a group leader. Commit 8e2527b74 makes the detached inner Bash publish $BASHPID after session creation, waits for that readiness before wrapper exit, verifies exact start ticks/PGID/SID, and cleans up via exact-generation termination. Verification: 11 targeted lifecycle/PID tests, 634 complete native guard+lease tests, focused Python 3.11/3.12/3.13 matrix, repeated regression runs, Ruff, mutation scan, and secret scan passed. Full make test passed the changed regression and 18,890 other tests, then hit unrelated real-clock waiter-priority flake tracked as OOMPAH-949; that isolated test passed 20 immediate reruns.
---
author: oompah
created: 2026-08-09 10:20
---
Removed the detached descendant regression's transient setsid PID race by introducing an inner-shell readiness handshake, exact process-generation/session assertions, and exact-generation cleanup without weakening native capacity fencing. Commit 8e2527b74 is pushed. Python 3.11-3.13 focused matrix and 634 native guard/lease tests pass; full gate passed OOMPAH-946 and exposed separate OOMPAH-949.
---
author: oompah
created: 2026-08-09 11:09
---
Branch quality gate passed for `8e2527b74e958127861621fdbcebb627d0929e24` using `make test` in 159.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-09 11:17
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 11:57
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 11:57
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 12:04
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- commit_hash: 8e2527b74e958127861621fdbcebb627d0929e24
- readiness_handshake: Inner bash publishes BASHPID after setsid
- cleanup: exact-generation termination
---
author: oompah
created: 2026-08-09 12:04
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 90, Tool calls: 42
- Tokens: 346 in / 12.3K out [12.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 36s
- Log: OOMPAH-946__20260809T115800Z.jsonl
---
author: oompah
created: 2026-08-09 13:58
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 13:58
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
