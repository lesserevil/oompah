---
id: OOMPAH-813
type: task
status: In Validation
priority: null
title: Fence revoked accepted-submission worker exits with the resolved project
parent: OOMPAH-768
children: []
blocked_by:
- OOMPAH-782
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T23:50:36.091912Z'
updated_at: '2026-08-05T01:11:33.166356Z'
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
  task_branch: OOMPAH-813
  base_branch: epic-OOMPAH-768
  base_sha: a3948097f27f4e84ac0f2375408ac05f4e419d2c
  head_sha: eb5d206f2fc040698808130b2629a997c3c9b953
  integrated_sha: eb5d206f2fc040698808130b2629a997c3c9b953
  submitted_at: '2026-08-05T00:26:52.430468+00:00'
  updated_at: '2026-08-05T00:45:57.410703+00:00'
  dependency_heads:
    OOMPAH-782: a3948097f27f4e84ac0f2375408ac05f4e419d2c
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2d68a82cf57b
    project_id: proj-14849f1b
    task_id: OOMPAH-813
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cf287da8ca8c3edc626b125a6e1b4d1da7c80ee201d4e8c38ea79184375a665
    attempts:
    - version: 1
      attempt_id: attempt-fa066f51e77c
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9cf287da8ca8c3edc626b125a6e1b4d1da7c80ee201d4e8c38ea79184375a665
      created_at: '2026-08-05T00:47:09.754765+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-05T00:47:09.754765+00:00'
      branch_key: OOMPAH-813
      failure_classification: policy_incompatibility
      ended_at: '2026-08-05T01:04:13.231991+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-05T01:04:23.231963+00:00'
    - version: 1
      attempt_id: attempt-1826e8832378
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9cf287da8ca8c3edc626b125a6e1b4d1da7c80ee201d4e8c38ea79184375a665
      created_at: '2026-08-05T01:05:18.465574+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-05T01:05:18.465574+00:00'
      branch_key: OOMPAH-813
      candidate_rotation_count: 1
      failure_classification: policy_incompatibility
      ended_at: '2026-08-05T01:10:58.724802+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-05T01:11:18.724775+00:00'
    - version: 1
      attempt_id: attempt-b5b143d24221
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9cf287da8ca8c3edc626b125a6e1b4d1da7c80ee201d4e8c38ea79184375a665
      created_at: '2026-08-05T01:11:22.915135+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-05T01:11:22.915135+00:00'
      branch_key: OOMPAH-813
      candidate_rotation_count: 2
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-05T00:46:11.334005+00:00'
    updated_at: '2026-08-05T01:11:22.915135+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-fa066f51e77c
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cf287da8ca8c3edc626b125a6e1b4d1da7c80ee201d4e8c38ea79184375a665
    created_at: '2026-08-05T00:47:09.754765+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-05T00:47:09.754765+00:00'
    branch_key: OOMPAH-813
    failure_classification: policy_incompatibility
    ended_at: '2026-08-05T01:04:13.231991+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-05T01:04:23.231963+00:00'
  - version: 1
    attempt_id: attempt-1826e8832378
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cf287da8ca8c3edc626b125a6e1b4d1da7c80ee201d4e8c38ea79184375a665
    created_at: '2026-08-05T01:05:18.465574+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-05T01:05:18.465574+00:00'
    branch_key: OOMPAH-813
    candidate_rotation_count: 1
    failure_classification: policy_incompatibility
    ended_at: '2026-08-05T01:10:58.724802+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-05T01:11:18.724775+00:00'
  - version: 1
    attempt_id: attempt-b5b143d24221
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9cf287da8ca8c3edc626b125a6e1b4d1da7c80ee201d4e8c38ea79184375a665
    created_at: '2026-08-05T01:11:22.915135+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-05T01:11:22.915135+00:00'
    branch_key: OOMPAH-813
    candidate_rotation_count: 2
oompah.task_costs:
  total_input_tokens: 104
  total_output_tokens: 2871
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 104
      output_tokens: 2871
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 63
    output_tokens: 1814
    cost_usd: 0.0
    recorded_at: '2026-08-05T01:04:11.116669+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 41
    output_tokens: 1057
    cost_usd: 0.0
    recorded_at: '2026-08-05T01:10:43.077672+00:00'
---
## Summary

Bug reproduction: in Orchestrator._on_worker_exit, the accepted_submission_record && revoked path calls _handle_revoked_submission_exit(project_id=project_id, ...) before project_id is assigned later in the method. A revoked worker that has already submitted therefore raises NameError instead of executing the safety recovery path. This predates the durable-domain stack but is present in its exact review head and Ruff reports F821. Implementation scope: resolve the project identity before any revoked-submission branch, preserve exact project/task/run authority fencing, and keep later worker-exit handling on the same resolved project without shadowing or cross-project fallback. Relevant code: oompah/orchestrator.py _on_worker_exit and _handle_revoked_submission_exit. Required tests: exercise _on_worker_exit itself (not only the helper) with an accepted submission plus revoked authority; assert no NameError, exact project is forwarded, cross-project records cannot be handled, and ordinary non-revoked exit behavior is unchanged. Run focused worker-exit/submission-fencing suites and terminal mutation scan. Acceptance: every revoked accepted-submission exit deterministically reaches the project-scoped recovery handler and never reads an uninitialized identity.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 23:56
---
Implementation started on exact OOMPAH-782 base a3948097f in branch epic-OOMPAH-768--task-OOMPAH-813. Scope is the minimal _on_worker_exit project-identity initialization fix plus wrapper-level revoked, cross-project, and non-revoked regression coverage; branch will remain unsubmitted for ordered landing.
---
author: oompah
created: 2026-08-05 00:02
---
Implementation checkpoint: _on_worker_exit now freezes the exact live run project before cleanup/awaits, uses that same scope throughout later exit handling, and the revoked-submission helper rejects missing, changed, cross-project, or cross-task records without tracker mutation. Verification: 100 focused submission-fencing/run-identity/provider-retirement/task-handoff/auditor-exit tests passed; terminal mutation scan passed 8/8; focused Ruff F821 and diff checks passed.
---
author: oompah
created: 2026-08-05 00:03
---
Completed and pushed exact task head 7eada51f6fe7ea384c02317654c0b376183fb7af on epic-OOMPAH-768--task-OOMPAH-813, with direct parent a3948097f27f4e84ac0f2375408ac05f4e419d2c. Focused verification remains green: 100 tests, terminal mutation scan 8/8, Ruff F821, and diff check. Branch is clean and up to date with origin. Per ordered-landing handoff, OOMPAH-813 remains In Progress/claimed and has not been submitted; project owner should submit only after OOMPAH-782 lands.
---
author: oompah
created: 2026-08-05 00:04
---
Fixed revoked accepted-submission exit project fencing at exact head 7eada51f6fe7ea384c02317654c0b376183fb7af, directly based on OOMPAH-782 a3948097f. Wrapper/cross-project/non-revoked regressions included; 100 focused tests, terminal scan 8/8, Ruff F821 and diff checks pass.
---
author: oompah
created: 2026-08-05 00:19
---
Independent exact-head review found a second-order run-fencing race, reproduced in memory: _handle_revoked_submission_exit awaits preserve_worktree_changes; if a replacement RunningEntry is installed during that await, _remove_running_entry correctly returns false but the helper ignores it, clears replacement shared-claim state, and applies the retired run accepted record to the tracker. Reproduction at 7eada51f6: replacement entry preserved, both replacement claims cleared, one stale tracker update. Task returned to In Progress and claimed for repair. Add an interleaving regression and revalidate exact current run after the await/before every shared-state or tracker mutation; stale retired work must return with zero side effects.
---
author: oompah
created: 2026-08-05 00:21
---
Acceptance-blocker repair implemented: revoked submission recovery now uses the identity-safe running-entry removal as its final post-preservation compare-and-remove and returns without clearing claims or touching tracker task data when a replacement generation owns the slot. Added deterministic executor interleaving regression that installs a replacement during preserve_worktree_changes and verifies running/claimed/claimed_issues remain intact with no stale tracker fetch/update. Focused matrix passes 101 tests; Ruff F821, git diff --check, and terminal mutation scan 8/8 pass. Preparing commit/push; task remains unsubmitted and claimed for coordinator re-audit.
---
author: oompah
created: 2026-08-05 00:22
---
Acceptance repair completed and pushed at eb5d206f2fc040698808130b2629a997c3c9b953 on OOMPAH-813, ordinary fast-forward from 7eada51f6. The helper now atomically proves the retired entry still owns state after the preservation await; a superseded exit returns before claim cleanup or tracker access. Deterministic regression installs a replacement from preserve_worktree_changes and verifies replacement running/claimed/claimed_issues plus zero stale tracker fetch/update. Verification: exact regression 1/1; focused submission-fencing/run-identity/provider-retirement/task-handoff/auditor-exit matrix 101/101; Ruff F821; git diff --check; terminal mutation scan 8/8. Branch is clean and up to date with origin. OOMPAH-813 was not submitted and its owner claim was not released.
---
author: oompah
created: 2026-08-05 00:26
---
Independent exact-head acceptance audit found no blockers at eb5d206f2fc040698808130b2629a997c3c9b953. It verified project identity is frozen before cleanup awaits, the post-preservation identity CAS is performed under the retry-authority lock, CAS loss returns before every claim/token/tracker mutation, and replacement-generation plus cross-project/non-revoked behavior remains covered. Read-only audit checks: focused race/compatibility 9 passed, Ruff F821, diff check.
---
author: oompah
created: 2026-08-05 00:26
---
Fixed revoked accepted-submission exit fencing at eb5d206f: exact project scope, post-await generation CAS, and deterministic replacement-run regression; 101 focused tests plus independent acceptance audit pass.
---
author: oompah
created: 2026-08-05 00:46
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-05 00:47
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-05 00:47
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 01:04
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 38
- Tokens: 63 in / 1.8K out [1.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 16m 50s
- Log: OOMPAH-813__20260805T004730Z.jsonl
---
author: oompah
created: 2026-08-05 01:04
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-05 01:05
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-05 01:05
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-05 01:10
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 0, Tool calls: 22
- Tokens: 41 in / 1.1K out [1.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 57s
- Log: OOMPAH-813__20260805T010602Z.jsonl
---
author: oompah
created: 2026-08-05 01:11
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-05 01:11
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-05 01:11
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
