---
id: OOMPAH-545
type: epic
status: In Validation
priority: 0
title: Make task dependencies finish-order constraints
parent: null
children:
- OOMPAH-546
- OOMPAH-547
- OOMPAH-548
- OOMPAH-549
blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-07-29T16:21:51.688684Z'
updated_at: '2026-08-05T19:39:36.963433Z'
work_branch: epic-OOMPAH-545
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/579
review_number: '579'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/579
oompah.review_number: '579'
oompah.work_branch: epic-OOMPAH-545
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-668f8211da16
    project_id: proj-14849f1b
    task_id: OOMPAH-545
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: add0e4e090f73f0d9b572c9b1a50e5f64e1f2ddc60b05e43464871e9107eecfa
    attempts:
    - version: 1
      attempt_id: attempt-4f0c841efb2a
      target_state: Archived
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: add0e4e090f73f0d9b572c9b1a50e5f64e1f2ddc60b05e43464871e9107eecfa
      created_at: '2026-08-05T19:25:46.009159+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T19:25:46.009159+00:00'
      branch_key: epic-OOMPAH-545
      failure_classification: policy_incompatibility
      ended_at: '2026-08-05T19:34:09.034345+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-05T19:34:19.034314+00:00'
    - version: 1
      attempt_id: attempt-be621b408a9a
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: add0e4e090f73f0d9b572c9b1a50e5f64e1f2ddc60b05e43464871e9107eecfa
      created_at: '2026-08-05T19:39:35.475470+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-05T19:39:35.475470+00:00'
      branch_key: epic-OOMPAH-545
      candidate_rotation_count: 1
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T19:23:58.398298+00:00'
    updated_at: '2026-08-05T19:39:35.475470+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4f0c841efb2a
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: add0e4e090f73f0d9b572c9b1a50e5f64e1f2ddc60b05e43464871e9107eecfa
    created_at: '2026-08-05T19:25:46.009159+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T19:25:46.009159+00:00'
    branch_key: epic-OOMPAH-545
    failure_classification: policy_incompatibility
    ended_at: '2026-08-05T19:34:09.034345+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-05T19:34:19.034314+00:00'
  - version: 1
    attempt_id: attempt-be621b408a9a
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: add0e4e090f73f0d9b572c9b1a50e5f64e1f2ddc60b05e43464871e9107eecfa
    created_at: '2026-08-05T19:39:35.475470+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-05T19:39:35.475470+00:00'
    branch_key: epic-OOMPAH-545
    candidate_rotation_count: 1
oompah.task_costs:
  total_input_tokens: 32
  total_output_tokens: 828
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 32
      output_tokens: 828
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 32
    output_tokens: 828
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:34:04.752009+00:00'
---
## Summary

Goal

Change normal task dependencies from dispatch/start barriers into ordered-completion constraints, while retaining an explicit hard-start relationship for the rare work that truly cannot begin early.

Implementation scope

Introduce the Ready to Integrate lifecycle and durable integration metadata; add finish-order and hard-start dependency semantics with inheritance from parent epics and cycle validation; add a worker submission handoff that stages child work for integration instead of allowing direct Done; update all tracker adapters, status rollups, APIs, dashboard surfaces, prompts, and operator documentation. Integrate with the terminal-transition coordinator so only integrated, audited code reaches Done.

Acceptance criteria

Finish dependencies do not prevent agent dispatch, hard-start dependencies do, Ready to Integrate is visible and restart-safe, direct child Done cannot bypass submission/integration, dependency cycles fail with actionable diagnostics, all tracker backends preserve the new metadata, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 16:23
---
Claimed by the interactive Codex session for the owner-requested parallel-epic execution implementation. Keep human-only; do not dispatch another worker. Work will be completed, tested, pushed, and handed off through the parent epic.
---
author: oompah
created: 2026-07-29 17:57
---
Implementation is complete on epic-OOMPAH-545. Full project gate passed: 13,213 tests passed, 7 skipped. Final rebase, merge, and deployment are in progress; this task remains human-owned and must not be dispatched.
---
author: oompah
created: 2026-08-05 19:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-05 19:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 19:26
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 19:34
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 17
- Tokens: 32 in / 828 out [860 total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 59s
- Log: OOMPAH-545__20260805T192620Z.jsonl
---
author: oompah
created: 2026-08-05 19:34
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
<!-- COMMENTS:END -->
