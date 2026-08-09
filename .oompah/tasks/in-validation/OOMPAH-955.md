---
id: OOMPAH-955
type: bug
status: In Validation
priority: 1
title: Prevent long durable effects from head-of-line blocking control jobs
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T11:49:56.915594Z'
updated_at: '2026-08-09T16:02:51.705704Z'
work_branch: OOMPAH-955
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-955
  base_branch: epic-OOMPAH-940
  base_sha: 41a158291ad932b232e9ebc4dcff5b0357d9f57b
  head_sha: fc1c8dc993964b34fbd60a008654fa8ca315b54f
  submitted_at: '2026-08-09T12:18:24.209775+00:00'
  updated_at: '2026-08-09T12:18:24.209775+00:00'
oompah.work_branch: OOMPAH-955
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-d341be5cbd4d
    project_id: proj-14849f1b
    task_id: OOMPAH-955
    digest: e61d6225c423b72632a018c93b66129aded2d509f9e82223137b34ac56605b1e
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-d341be5cbd4d
    project_id: proj-14849f1b
    task_id: OOMPAH-955
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e61d6225c423b72632a018c93b66129aded2d509f9e82223137b34ac56605b1e
    attempts:
    - version: 1
      attempt_id: attempt-c2773209073c
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e61d6225c423b72632a018c93b66129aded2d509f9e82223137b34ac56605b1e
      created_at: '2026-08-09T14:33:41.184959+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T14:33:41.184959+00:00'
      branch_key: OOMPAH-955
      selected_ref: fc1c8dc993964b34fbd60a008654fa8ca315b54f
      selected_sha: fc1c8dc993964b34fbd60a008654fa8ca315b54f
      failure_classification: scheduler_pause
      ended_at: '2026-08-09T15:51:25.765873+00:00'
      failure_reason: graceful restart interrupted auditor before verdict
    - version: 1
      attempt_id: attempt-6b8667b926c1
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e61d6225c423b72632a018c93b66129aded2d509f9e82223137b34ac56605b1e
      created_at: '2026-08-09T16:02:35.226177+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T16:02:35.226177+00:00'
      branch_key: OOMPAH-955
      selected_ref: fc1c8dc993964b34fbd60a008654fa8ca315b54f
      selected_sha: fc1c8dc993964b34fbd60a008654fa8ca315b54f
      candidate_rotation_count: 1
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:51:41.055249+00:00'
    selected_ref: fc1c8dc993964b34fbd60a008654fa8ca315b54f
    selected_sha: fc1c8dc993964b34fbd60a008654fa8ca315b54f
    updated_at: '2026-08-09T16:02:35.226177+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-c2773209073c
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e61d6225c423b72632a018c93b66129aded2d509f9e82223137b34ac56605b1e
    created_at: '2026-08-09T14:33:41.184959+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T14:33:41.184959+00:00'
    branch_key: OOMPAH-955
    selected_ref: fc1c8dc993964b34fbd60a008654fa8ca315b54f
    selected_sha: fc1c8dc993964b34fbd60a008654fa8ca315b54f
    failure_classification: scheduler_pause
    ended_at: '2026-08-09T15:51:25.765873+00:00'
    failure_reason: graceful restart interrupted auditor before verdict
  - version: 1
    attempt_id: attempt-6b8667b926c1
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e61d6225c423b72632a018c93b66129aded2d509f9e82223137b34ac56605b1e
    created_at: '2026-08-09T16:02:35.226177+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T16:02:35.226177+00:00'
    branch_key: OOMPAH-955
    selected_ref: fc1c8dc993964b34fbd60a008654fa8ca315b54f
    selected_sha: fc1c8dc993964b34fbd60a008654fa8ca315b54f
    candidate_rotation_count: 1
oompah.task_costs:
  total_input_tokens: 54
  total_output_tokens: 21
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 54
      output_tokens: 21
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 54
    output_tokens: 21
    cost_usd: 0.0
    recorded_at: '2026-08-09T15:50:59.015447+00:00'
---
## Summary

Live production reproducer on 2026-08-09: workflow job OOMPAH-951 standalone_delivery held an accepted lease and renewed normally while waiting on the sole validation-resource slot owned by OOMPAH-939, but WorkflowRuntime._run_due awaited DurableWorkflowWorker.run_once inline. That one long effect prevented independent priority-0 authority revocation, priority-10 validation submission, controller observation, state publication, and tick completion for more than 900 seconds, arming the dispatch-loop-stale alert. Review capacity was available and the queued jobs were otherwise eligible. No active task covers this; OOMPAH-953 only removes network-backed hot polling. Scope: execute durable effects with bounded concurrency or lane isolation so long data-plane gates cannot head-of-line block control-plane jobs; reserve at least one control slot/lane; preserve database-enforced same-project/task serialization, fair project claiming, exact leases/heartbeats/checkpoints, effect idempotency, shutdown/drain semantics, and bounded resource use. Required tests: block standalone delivery on validation capacity, enqueue independent exact authority revocation and validation submission, and prove both complete plus state/controller generations advance within a deterministic bound; same-task effects remain serialized; configured concurrency and reserved control capacity are never exceeded; crash/restart/drain produce no duplicate effect or lost waiter; multi-project fairness remains. Acceptance: a waiting/running full gate cannot stale the dispatch loop or delay independent control work, live telemetry remains current, and focused/full gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 12:06
---
Implemented on branch OOMPAH-955 at 5bb0803b396d0cd7d7cd5837c31d05742e99aba0 (target epic-OOMPAH-940). Workflow reconciliation now claims and retains durable effects in bounded detached lanes: at least one exact control slot admits revocation/submission/recovery while the shared lane handles general effects. Completion wakes a coalesced refresh; graceful drain covers claimed/pre-start invocations; independent worker heartbeats/checkpoints and SQLite same-task/fair-project fences remain authoritative. Added env-only concurrency controls and health telemetry. Verification: 317 focused runtime/job/worker/config tests passed; 294/295 adjacent implementation/integration/review/epic/incident tests passed, with only the pre-existing OOMPAH-748 aggregate failure addressed separately by OOMPAH-954; task-status mutation scan and secret scan passed; git diff --check clean.
---
author: oompah
created: 2026-08-09 12:07
---
Implemented bounded detached workflow effects with a reserved control lane, independent lease heartbeats, completion-driven replenishment, safe drain/restart recovery, configuration and telemetry, plus deterministic HOL/concurrency/serialization/lease regressions. Commit 5bb0803b396d0cd7d7cd5837c31d05742e99aba0 pushed.
---
author: oompah
created: 2026-08-09 12:18
---
Addressed independent-review blocker in fc1c8dc993964b34fbd60a008654fa8ca315b54f: a runtime-owned async admission critical section now spans capacity observation, awaited exact claims, and retained-task publication, so overlapping reconcile_async/_run_due callers cannot spend the same reserved/shared slot. Added a deterministic two-caller race regression that suspends the first claim at the former gap and proves control=1, shared=3, total=4. Verification: 318 focused tests passed; task-status mutation scan, secret scan, and git diff --check passed. Branch pushed clean/up-to-date; no restart.
---
author: oompah
created: 2026-08-09 12:18
---
Review blocker fixed: workflow effect admission is serialized across async claims, with deterministic concurrent-call bound coverage. Review-ready head fc1c8dc993964b34fbd60a008654fa8ca315b54f pushed.
---
author: oompah
created: 2026-08-09 12:51
---
Worked around OOMPAH-958 durable integration lease deadlock: both accepted commits are patch-equivalent in origin/epic-OOMPAH-940 at 1ab5776d8. Reconciled to Done from authoritative target evidence.
---
author: oompah
created: 2026-08-09 12:51
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 14:33
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 14:33
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-09 15:51
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 6, Tool calls: 2
- Tokens: 54 in / 21 out [75 total]
- Cost: $0.0000
- Exit: scheduler_pause, Duration: 1h 17m 15s
- Log: OOMPAH-955__20260809T143358Z.jsonl
---
author: oompah
created: 2026-08-09 15:51
---
Auditor attempt ended: graceful restart interrupted auditor before verdict. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-09 16:02
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 16:02
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
