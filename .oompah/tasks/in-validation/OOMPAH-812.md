---
id: OOMPAH-812
type: task
status: In Validation
priority: null
title: Drain synthetic long-tick ordering fixtures under full-gate load
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T22:47:56.569040Z'
updated_at: '2026-08-04T23:26:31.210376Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-812
target_branch: epic-OOMPAH-768
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.target_branch: epic-OOMPAH-768
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-812
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-768--task-OOMPAH-812
  base_branch: epic-OOMPAH-768
  base_sha: a744be37d42047e25e6fc62a6a64878c187290e0
  head_sha: 1230456cc7834d14b8064d73e1742734ab670d2a
  integrated_sha: 1230456cc7834d14b8064d73e1742734ab670d2a
  submitted_at: '2026-08-04T22:52:34.629625+00:00'
  updated_at: '2026-08-04T23:13:37.122553+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-7f5bb039e5df
    project_id: proj-14849f1b
    task_id: OOMPAH-812
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5cc3b17ae25ba98859760a47dbbd8c39110fd131c8b1ce951676f4fc85cceaf2
    attempts:
    - version: 1
      attempt_id: attempt-7697c4ded953
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5cc3b17ae25ba98859760a47dbbd8c39110fd131c8b1ce951676f4fc85cceaf2
      created_at: '2026-08-04T23:15:15.985975+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T23:15:15.985975+00:00'
      branch_key: epic-OOMPAH-768--task-OOMPAH-812
      failure_classification: policy_incompatibility
      ended_at: '2026-08-04T23:25:36.762394+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-04T23:25:46.762365+00:00'
    - version: 1
      attempt_id: attempt-a804febef756
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 5cc3b17ae25ba98859760a47dbbd8c39110fd131c8b1ce951676f4fc85cceaf2
      created_at: '2026-08-04T23:26:29.746815+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T23:26:29.746815+00:00'
      branch_key: epic-OOMPAH-768--task-OOMPAH-812
      candidate_rotation_count: 1
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-04T23:13:49.092144+00:00'
    updated_at: '2026-08-04T23:26:29.746815+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-7697c4ded953
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5cc3b17ae25ba98859760a47dbbd8c39110fd131c8b1ce951676f4fc85cceaf2
    created_at: '2026-08-04T23:15:15.985975+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T23:15:15.985975+00:00'
    branch_key: epic-OOMPAH-768--task-OOMPAH-812
    failure_classification: policy_incompatibility
    ended_at: '2026-08-04T23:25:36.762394+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-04T23:25:46.762365+00:00'
  - version: 1
    attempt_id: attempt-a804febef756
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 5cc3b17ae25ba98859760a47dbbd8c39110fd131c8b1ce951676f4fc85cceaf2
    created_at: '2026-08-04T23:26:29.746815+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T23:26:29.746815+00:00'
    branch_key: epic-OOMPAH-768--task-OOMPAH-812
    candidate_rotation_count: 1
oompah.task_costs:
  total_input_tokens: 47
  total_output_tokens: 1711
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 47
      output_tokens: 1711
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 47
    output_tokens: 1711
    cost_usd: 0.0
    recorded_at: '2026-08-04T23:25:34.559016+00:00'
---
## Summary

Live exact-head gate reproduction on OOMPAH-781 at 41f717cd46baf4e8ba455586b39ce9e67d25a471: make test passed 15,741 tests but failed tests/test_long_tick_regression.py::TestSyntheticSlowJobs::test_heal_repos_always_runs_after_dispatch_needed after 643s. The test asserts dispatch-before-maintenance ordering, but it constructs a real Orchestrator, schedules multiple fire-and-forget executor futures/stores in _tick(), awaits only _maintenance_future, and exits without draining/closing the other owned background work. The exact test passes focused and 100/100 direct same-process invocations, so this is a full-load lifecycle/timeout race adjacent to OOMPAH-805 rather than terminal-audit product behavior. Implementation scope: make this ordering fixture deterministic without weakening its structural assertion; stub irrelevant background lanes, synchronize on the actual maintenance action, and drain/close every orchestrator-owned future, pool, and durable store in finally. Give the test a lifecycle-sized timeout only if deterministic cleanup can legitimately exceed the global five-second unit budget under parallel load. Audit neighboring TestSyntheticSlowJobs fixtures for the same leak and repair only concrete cases. Required tests: the exact test repeated in one process, complete test_long_tick_regression module serially and with xdist, combined event-loop/long-tick/orchestrator fixture slice, terminal mutation scan, and the server exact full gate after landing. Acceptance: dispatch_needed always precedes heal_repos; no executor thread/future/store survives the test; the OOMPAH-781 combined gate can rerun without a load-only timeout.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 22:51
---
Implemented at exact head 1230456cc7834d14b8064d73e1742734ab670d2a. The ordering test now disables unrelated durable lanes, waits for its actual step-5b future, and drains every owned future/pool/store in finally under a lifecycle-sized timeout. Verification: exact test 1/1; 100/100 same-process invocations; module 14/14 serial and 14/14 with -n 4; combined event-loop/long-tick/orchestrator/Granian/GitHub fixture slice 284/284 with -n 4; terminal mutation scan 8/8; diff check clean.
---
author: oompah
created: 2026-08-04 22:52
---
Made the full-load synthetic ordering fixture deterministic and leak-free at 1230456cc; 100x repeat, serial/parallel module, 284-test combined fixture slice, and mutation scan pass.
---
author: oompah
created: 2026-08-04 23:13
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-04 23:15
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 23:15
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 23:25
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 29
- Tokens: 47 in / 1.7K out [1.8K total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 6s
- Log: OOMPAH-812__20260804T231541Z.jsonl
---
author: oompah
created: 2026-08-04 23:25
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
<!-- COMMENTS:END -->
