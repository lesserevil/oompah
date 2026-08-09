---
id: OOMPAH-949
type: bug
status: Merged
priority: 1
title: Make fresh-waiter priority regression independent of host scheduling
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T10:18:16.575025Z'
updated_at: '2026-08-09T16:31:44.167222Z'
work_branch: OOMPAH-949
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-949
  head_sha: 27c3685dc3d2e4aba8e852a88569795acd300fe7
  submitted_at: '2026-08-09T10:28:20.807004+00:00'
  updated_at: '2026-08-09T10:28:20.807004+00:00'
oompah.work_branch: OOMPAH-949
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-b5437e001a05
    project_id: proj-14849f1b
    task_id: OOMPAH-949
    digest: a4a47f04bfa3a98181764fe8e565906643b9e7d9425ebcc97a48b51e23617224
  - version: 1
    audit_id: audit-e418ec38f7a8
    project_id: proj-14849f1b
    task_id: OOMPAH-949
    digest: a4a47f04bfa3a98181764fe8e565906643b9e7d9425ebcc97a48b51e23617224
  oompah.terminal_override_records:
  - version: 1
    override_id: override-2ecd209cb4fa
    project_id: proj-14849f1b
    task_id: OOMPAH-949
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a4a47f04bfa3a98181764fe8e565906643b9e7d9425ebcc97a48b51e23617224
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner override after exact task head 27c3685dc3d2e4aba8e852a88569795acd300fe7
      was proven to be PR #762 head and contained in main; PR #762 merged as 73705cea7523925b2bec19bc374e0399351e9e3d
      with hosted Python 3.11/3.12/3.13 checks successful.'
    created_at: '2026-08-09T16:31:39.981869+00:00'
    selected_ref: 27c3685dc3d2e4aba8e852a88569795acd300fe7
    selected_sha: 27c3685dc3d2e4aba8e852a88569795acd300fe7
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b5437e001a05
    project_id: proj-14849f1b
    task_id: OOMPAH-949
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a4a47f04bfa3a98181764fe8e565906643b9e7d9425ebcc97a48b51e23617224
    attempts:
    - version: 1
      attempt_id: attempt-d2e60aa0a26e
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a4a47f04bfa3a98181764fe8e565906643b9e7d9425ebcc97a48b51e23617224
      created_at: '2026-08-09T12:34:27.673582+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T12:34:27.673582+00:00'
      branch_key: OOMPAH-949
      selected_ref: 27c3685dc3d2e4aba8e852a88569795acd300fe7
      selected_sha: 27c3685dc3d2e4aba8e852a88569795acd300fe7
      failure_classification: policy_incompatibility
      ended_at: '2026-08-09T12:57:02.602239+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-09T12:57:12.602200+00:00'
    - version: 1
      attempt_id: attempt-a35d2d44bcef
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a4a47f04bfa3a98181764fe8e565906643b9e7d9425ebcc97a48b51e23617224
      created_at: '2026-08-09T14:14:56.957941+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-09T14:14:56.957941+00:00'
      branch_key: OOMPAH-949
      selected_ref: 27c3685dc3d2e4aba8e852a88569795acd300fe7
      selected_sha: 27c3685dc3d2e4aba8e852a88569795acd300fe7
      candidate_rotation_count: 1
      failure_classification: scheduler_pause
      ended_at: '2026-08-09T15:50:49.470799+00:00'
      failure_reason: graceful restart interrupted auditor before verdict
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T12:27:15.737526+00:00'
    selected_ref: 27c3685dc3d2e4aba8e852a88569795acd300fe7
    selected_sha: 27c3685dc3d2e4aba8e852a88569795acd300fe7
    updated_at: '2026-08-09T15:50:49.470799+00:00'
  - version: 1
    audit_id: audit-e418ec38f7a8
    project_id: proj-14849f1b
    task_id: OOMPAH-949
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a4a47f04bfa3a98181764fe8e565906643b9e7d9425ebcc97a48b51e23617224
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-09T12:27:15.737526+00:00'
    selected_ref: 27c3685dc3d2e4aba8e852a88569795acd300fe7
    selected_sha: 27c3685dc3d2e4aba8e852a88569795acd300fe7
  attempt_history:
  - version: 1
    attempt_id: attempt-d2e60aa0a26e
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a4a47f04bfa3a98181764fe8e565906643b9e7d9425ebcc97a48b51e23617224
    created_at: '2026-08-09T12:34:27.673582+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T12:34:27.673582+00:00'
    branch_key: OOMPAH-949
    selected_ref: 27c3685dc3d2e4aba8e852a88569795acd300fe7
    selected_sha: 27c3685dc3d2e4aba8e852a88569795acd300fe7
    failure_classification: policy_incompatibility
    ended_at: '2026-08-09T12:57:02.602239+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-09T12:57:12.602200+00:00'
  - version: 1
    attempt_id: attempt-a35d2d44bcef
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a4a47f04bfa3a98181764fe8e565906643b9e7d9425ebcc97a48b51e23617224
    created_at: '2026-08-09T14:14:56.957941+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-09T14:14:56.957941+00:00'
    branch_key: OOMPAH-949
    selected_ref: 27c3685dc3d2e4aba8e852a88569795acd300fe7
    selected_sha: 27c3685dc3d2e4aba8e852a88569795acd300fe7
    candidate_rotation_count: 1
    failure_classification: scheduler_pause
    ended_at: '2026-08-09T15:50:49.470799+00:00'
    failure_reason: graceful restart interrupted auditor before verdict
oompah.task_costs:
  total_input_tokens: 315
  total_output_tokens: 279
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 315
      output_tokens: 279
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 294
    output_tokens: 60
    cost_usd: 0.0
    recorded_at: '2026-08-09T12:57:09.249377+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 21
    output_tokens: 219
    cost_usd: 0.0
    recorded_at: '2026-08-09T15:50:49.466520+00:00'
---
## Summary

Triggered by: OOMPAH-946

Full make test for OOMPAH-946 on 2026-08-09 reached 18,890 passing tests but intermittently failed tests/test_validation_resource_lease.py::test_cancelled_aged_waiter_does_not_transfer_protection: the fresh worker acquired before the fresh exact waiter. The test configures aging_seconds=0.01, so normal host scheduling can age the nominally fresh worker before the exact waiter is durably queued; 634-module coverage and 20 immediate isolated reruns passed. Determine whether the observed ordering is solely the real-clock fixture assumption or exposes a lease selection race. Make the regression deterministic with a controlled clock and explicit freshness boundary if production is correct, or repair the selection fence if exact work can lose while both waiters are provably fresh. Preserve bounded aging and no-starvation from OOMPAH-905, exact urgency for genuinely fresh waiters, FIFO within effective priority, cancellation cleanup, restart persistence, and capacity safety. Required tests: a cancelled aged waiter cannot transfer age; a fresh exact waiter overtakes a provably fresh worker; a genuinely aged worker still receives its fairness boost; repeated focused runs under artificial scheduling delay; complete make test. Acceptance: ordering assertions derive from explicit durable timestamps rather than sub-10ms scheduler timing and the full gate is stable under load.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:28
---
Investigation proved the full-gate ordering was correct production behavior: with aging_seconds=0.01, the observed ~210 ms xdist scheduling pause moved the worker across all 21 aging bands, so its starvation protection legitimately outranked the later exact waiter. Commit 27c3685dc keeps replacement waiters in an explicit 30-second aging band (630-second starvation window), artificially reproduces the 250 ms hosted pause, and asserts durable telemetry for the genuinely aged cancelled waiter and both fresh replacements before release. Production selection code is unchanged. Verification: the regression passed 10 consecutive runs; all 499 validation-resource lease tests passed; five focused priority/cancellation/restart/multiprocess tests, Ruff, terminal mutation scan, and secret scan passed. The preceding OOMPAH-946 full gate had already passed the other 18,890 tests before exposing this one test assumption.
---
author: oompah
created: 2026-08-09 10:28
---
Made the cancelled-waiter aging regression independent of host scheduling by using explicit durable freshness/starvation windows, reproducing the hosted scheduling gap, and asserting effective-priority evidence before capacity release. Production fairness behavior remains unchanged. Commit 27c3685dc is pushed; 499 lease tests and 10 repeated reproductions pass.
---
author: oompah
created: 2026-08-09 12:19
---
Exact branch gate passed at 27c3685dc3d2e4aba8e852a88569795acd300fe7: make test completed with 18,901 passed, 7 skipped, and 2 xfailed in 1,212.43 seconds. Opened protected-main PR #762 and enabled merge-when-green.
---
author: oompah
created: 2026-08-09 12:27
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 12:34
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 12:34
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 12:57
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-09 12:57
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 16
- Tokens: 294 in / 60 out [354 total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 38s
- Log: OOMPAH-949__20260809T123439Z.jsonl
---
author: oompah
created: 2026-08-09 14:15
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-09 14:15
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 15:50
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 13, Tool calls: 7
- Tokens: 21 in / 219 out [240 total]
- Cost: $0.0000
- Exit: scheduler_pause, Duration: 1h 35m 50s
- Log: OOMPAH-949__20260809T141513Z.jsonl
---
author: oompah
created: 2026-08-09 15:51
---
Auditor attempt ended: graceful restart interrupted auditor before verdict. A different independent auditor will be tried on the next scheduler tick.
---
<!-- COMMENTS:END -->
