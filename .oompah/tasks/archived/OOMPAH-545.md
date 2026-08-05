---
id: OOMPAH-545
type: epic
status: Archived
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
updated_at: '2026-08-05T20:02:05.530231Z'
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
  applied_result_attempts:
    attempt-be621b408a9a: '2026-08-05T20:00:26.687418+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-545
    target_state: Archived
    evidence_fingerprint: add0e4e090f73f0d9b572c9b1a50e5f64e1f2ddc60b05e43464871e9107eecfa
    audit_ids:
    - audit-668f8211da16
    kind: result
    applied: true
    retired_at: '2026-08-05T20:00:26.687425+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-545
    audit_id: audit-668f8211da16
    attempt_id: attempt-be621b408a9a
    target_state: Archived
    evidence_fingerprint: add0e4e090f73f0d9b572c9b1a50e5f64e1f2ddc60b05e43464871e9107eecfa
    status: Archived
    audit_ids:
    - audit-668f8211da16
    applied: true
    created_at: '2026-08-05T20:00:26.687435+00:00'
    applied_at: '2026-08-05T20:00:39.956779+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-668f8211da16
    project_id: proj-14849f1b
    task_id: OOMPAH-545
    target_state: Archived
    request_state: completed
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
      request_state: completed
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
      verdict: pass
      completed_at: '2026-08-05T20:00:26.687326+00:00'
      ended_at: '2026-08-05T20:00:26.687326+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T19:23:58.398298+00:00'
    updated_at: '2026-08-05T20:00:26.687326+00:00'
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
  total_input_tokens: 35
  total_output_tokens: 907
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 35
      output_tokens: 907
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 32
    output_tokens: 828
    cost_usd: 0.0
    recorded_at: '2026-08-05T19:34:04.752009+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 3
    output_tokens: 79
    cost_usd: 0.0
    recorded_at: '2026-08-05T20:02:02.921828+00:00'
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
author: oompah
created: 2026-08-05 19:39
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-05 19:39
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 20:00
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 31f8938b8 (PR #579, 2026-07-29)
- merge_confirmed_on_main: git merge-base --is-ancestor exit 0
- key_files_present: oompah/dependency_graph.py, oompah/statuses.py (READY_TO_INTEGRATE), oompah/integration_queue.py, oompah/integration_executor.py, oompah/coordination.py, docs/parallel-epic-integration.md
- focused_test_results: 310 tests across 11 suites, all pass
- working_tree_clean: git status: nothing to commit
- days_since_merge: 7
---
author: oompah
created: 2026-08-05 20:02
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 0, Tool calls: 49
- Tokens: 3 in / 79 out [82 total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 20s
- Log: OOMPAH-545__20260805T194002Z.jsonl
---
<!-- COMMENTS:END -->
