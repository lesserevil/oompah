---
id: OOMPAH-836
type: task
status: In Validation
priority: 1
title: Bind integration delivery and recovery to exact durable handlers
parent: OOMPAH-804
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:38.407330Z'
updated_at: '2026-08-06T11:33:32.971275Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: OOMPAH-836
  base_branch: epic-OOMPAH-804
  base_sha: c31b8d32aeeee2fe4de82c9b51614a84f5937770
  head_sha: c31b8d32aeeee2fe4de82c9b51614a84f5937770
  integrated_sha: c31b8d32aeeee2fe4de82c9b51614a84f5937770
  submitted_at: '2026-08-06T10:06:11.312451+00:00'
  updated_at: '2026-08-06T11:27:26.787746+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-7d503699759f
    project_id: proj-14849f1b
    task_id: OOMPAH-836
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: dfbe5d34de3178568e4cf0c1f7a94e06865a86adb1924692024bbf08ab54303a
    attempts:
    - version: 1
      attempt_id: attempt-d249fe24dc07
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: dfbe5d34de3178568e4cf0c1f7a94e06865a86adb1924692024bbf08ab54303a
      created_at: '2026-08-06T11:28:00.458665+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T11:28:00.458665+00:00'
      branch_key: OOMPAH-836
      failure_classification: policy_incompatibility
      ended_at: '2026-08-06T11:32:55.757297+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-06T11:33:05.757265+00:00'
    - version: 1
      attempt_id: attempt-7baf168299fa
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: dfbe5d34de3178568e4cf0c1f7a94e06865a86adb1924692024bbf08ab54303a
      created_at: '2026-08-06T11:33:21.069364+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-06T11:33:21.069364+00:00'
      branch_key: OOMPAH-836
      candidate_rotation_count: 1
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-06T11:27:29.266985+00:00'
    updated_at: '2026-08-06T11:33:21.069364+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d249fe24dc07
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: dfbe5d34de3178568e4cf0c1f7a94e06865a86adb1924692024bbf08ab54303a
    created_at: '2026-08-06T11:28:00.458665+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T11:28:00.458665+00:00'
    branch_key: OOMPAH-836
    failure_classification: policy_incompatibility
    ended_at: '2026-08-06T11:32:55.757297+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-06T11:33:05.757265+00:00'
  - version: 1
    attempt_id: attempt-7baf168299fa
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: dfbe5d34de3178568e4cf0c1f7a94e06865a86adb1924692024bbf08ab54303a
    created_at: '2026-08-06T11:33:21.069364+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-06T11:33:21.069364+00:00'
    branch_key: OOMPAH-836
    candidate_rotation_count: 1
oompah.task_costs:
  total_input_tokens: 69
  total_output_tokens: 3838
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 69
      output_tokens: 3838
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 69
    output_tokens: 3838
    cost_usd: 0.0
    recorded_at: '2026-08-06T11:32:53.404409+00:00'
---
## Summary

Implement production task-scoped handlers for all seven IntegrationWorkflow actions: landing refresh, terminal stage, historical audit replay, integration attempt, integration recovery, standalone delivery, and epic-branch reconciliation. Split the one-item integration executor and queue completion/coordination/audit staging from _process_integration_queues; make the workflow job lease the enforce-mode authority rather than a competing IntegrationQueue lease. Extract one-candidate standalone forge delivery and exact branch/rebase repair without invoking project-wide sweeps. Extend action-specific observations/results so maintenance actions do not unconditionally call integrate(). Relevant files: oompah/integration_workflow.py, oompah/workflow_runtime.py or typed adapters, integration executor/queue, orchestrator delivery/replay/standalone/branch repair paths. Required tests: immutable private heads, changed parent ancestry, executor crash and restart, retry/recovery, same-head replay, historical terminal staging, standalone review creation/adoption, multi-project routing, effect receipts, and enforce single-writer assertions. Acceptance: each action has an exact project/task handler and verification receipt; restart resumes rather than duplicates; no global sweep or second queue owner escapes the job boundary.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 09:39
---
Integration delivery/recovery handlers and regression coverage are complete, with exact commit 867be73e included in canonical validated composition f89c477d. Resubmitting canonical head after OOMPAH-858 task-scoped nested-delivery recovery so gate, integration, and audit share one exact candidate.
---
author: oompah
created: 2026-08-06 10:06
---
Shared exact-gate regression repair propagated to canonical head c31b8d32a; 81 formerly failing module tests pass and independent review accepted.
---
author: oompah
created: 2026-08-06 11:27
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-06 11:28
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 11:28
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-06 11:32
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 51
- Tokens: 69 in / 3.8K out [3.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 50s
- Log: OOMPAH-836__20260806T112812Z.jsonl
---
author: oompah
created: 2026-08-06 11:33
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-06 11:33
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-06 11:33
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
