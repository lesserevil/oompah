---
id: OOMPAH-451
type: epic
status: In Validation
priority: 1
title: Restore GitLab parity stranded after the OOMPAH-318 epic merge
parent: null
children:
- OOMPAH-452
- OOMPAH-453
- OOMPAH-454
- OOMPAH-455
- OOMPAH-456
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T12:34:07.972119Z'
updated_at: '2026-08-04T15:46:52.300755Z'
work_branch: epic-OOMPAH-451
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/560
review_number: '560'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/560
oompah.review_number: '560'
oompah.work_branch: epic-OOMPAH-451
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-5b11000acb47: '2026-08-04T15:25:41.704049+00:00'
    infrastructure-exhausted-audit-24a26411808a-3: '2026-08-04T15:45:14.970779+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-451
    target_state: Archived
    evidence_fingerprint: ec2faf89a761d26e33c737e46d2bbf72c87afc3f6eb9eef479e9cd305f0777df
    audit_ids:
    - audit-c9d9897dbd67
    kind: result
    applied: true
    retired_at: '2026-08-04T15:25:41.704061+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-451
    target_state: Done
    evidence_fingerprint: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
    audit_ids:
    - audit-24a26411808a
    kind: result
    applied: true
    retired_at: '2026-08-04T15:45:14.970791+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-451
    audit_id: audit-c9d9897dbd67
    attempt_id: attempt-5b11000acb47
    target_state: Archived
    evidence_fingerprint: ec2faf89a761d26e33c737e46d2bbf72c87afc3f6eb9eef479e9cd305f0777df
    status: Needs Human
    audit_ids:
    - audit-c9d9897dbd67
    applied: true
    created_at: '2026-08-04T15:25:41.704076+00:00'
    applied_at: '2026-08-04T15:25:50.985609+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-451
    audit_id: audit-24a26411808a
    attempt_id: infrastructure-exhausted-audit-24a26411808a-3
    target_state: Done
    evidence_fingerprint: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
    status: Needs Human
    audit_ids:
    - audit-24a26411808a
    applied: true
    created_at: '2026-08-04T15:45:14.970804+00:00'
    applied_at: '2026-08-04T15:45:24.355908+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c9d9897dbd67
    project_id: proj-14849f1b
    task_id: OOMPAH-451
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec2faf89a761d26e33c737e46d2bbf72c87afc3f6eb9eef479e9cd305f0777df
    attempts:
    - version: 1
      attempt_id: attempt-5b11000acb47
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: ec2faf89a761d26e33c737e46d2bbf72c87afc3f6eb9eef479e9cd305f0777df
      created_at: '2026-08-04T15:20:20.495612+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T15:20:20.495612+00:00'
      branch_key: epic-OOMPAH-451
      verdict: fail
      failure_classification: unsafe_archive
      completed_at: '2026-08-04T15:25:41.703922+00:00'
      ended_at: '2026-08-04T15:25:41.703922+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T15:19:04.185104+00:00'
    updated_at: '2026-08-04T15:25:41.703922+00:00'
  - version: 1
    audit_id: audit-24a26411808a
    project_id: proj-14849f1b
    task_id: OOMPAH-451
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
    attempts:
    - version: 1
      attempt_id: attempt-113362499b8a
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
      created_at: '2026-08-04T15:30:22.551965+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T15:30:22.551965+00:00'
      branch_key: epic-OOMPAH-451
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T15:30:31.717402+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-451 (tried: origin/epic-OOMPAH-451, origin/OOMPAH-451)'
      next_retry_at: '2026-08-04T15:30:41.717371+00:00'
    - version: 1
      attempt_id: attempt-fc4d2d1a7431
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
      created_at: '2026-08-04T15:38:36.877946+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T15:38:36.877946+00:00'
      branch_key: epic-OOMPAH-451
      candidate_rotation_count: 1
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T15:38:44.291833+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-451 (tried: origin/epic-OOMPAH-451, origin/OOMPAH-451)'
      next_retry_at: '2026-08-04T15:39:04.291804+00:00'
    - version: 1
      attempt_id: attempt-740bdd35afc7
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
      created_at: '2026-08-04T15:39:05.793095+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-04T15:39:05.793095+00:00'
      branch_key: epic-OOMPAH-451
      candidate_rotation_count: 2
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T15:39:17.487484+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-451 (tried: origin/epic-OOMPAH-451, origin/OOMPAH-451)'
      next_retry_at: '2026-08-04T15:39:57.487455+00:00'
    - version: 1
      attempt_id: infrastructure-exhausted-audit-24a26411808a-3
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
      verdict: needs_human
      failure_classification: infrastructure_error
      created_at: '2026-08-04T15:45:14.970709+00:00'
      completed_at: '2026-08-04T15:45:14.970709+00:00'
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T15:22:35.004302+00:00'
    updated_at: '2026-08-04T15:45:14.970709+00:00'
  - version: 1
    audit_id: audit-c1c7f0c558af
    project_id: proj-14849f1b
    task_id: OOMPAH-451
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T15:22:35.004302+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5b11000acb47
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ec2faf89a761d26e33c737e46d2bbf72c87afc3f6eb9eef479e9cd305f0777df
    created_at: '2026-08-04T15:20:20.495612+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T15:20:20.495612+00:00'
    branch_key: epic-OOMPAH-451
  - version: 1
    attempt_id: attempt-113362499b8a
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
    created_at: '2026-08-04T15:30:22.551965+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T15:30:22.551965+00:00'
    branch_key: epic-OOMPAH-451
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T15:30:31.717402+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-451 (tried: origin/epic-OOMPAH-451, origin/OOMPAH-451)'
    next_retry_at: '2026-08-04T15:30:41.717371+00:00'
  - version: 1
    attempt_id: attempt-fc4d2d1a7431
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
    created_at: '2026-08-04T15:38:36.877946+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T15:38:36.877946+00:00'
    branch_key: epic-OOMPAH-451
    candidate_rotation_count: 1
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T15:38:44.291833+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-451 (tried: origin/epic-OOMPAH-451, origin/OOMPAH-451)'
    next_retry_at: '2026-08-04T15:39:04.291804+00:00'
  - version: 1
    attempt_id: attempt-740bdd35afc7
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f94586f4c9bd8064b7231df299d8b94ebac70190a3c18e373cdb4e2c4f67f348
    created_at: '2026-08-04T15:39:05.793095+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-04T15:39:05.793095+00:00'
    branch_key: epic-OOMPAH-451
    candidate_rotation_count: 2
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T15:39:17.487484+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-451 (tried: origin/epic-OOMPAH-451, origin/OOMPAH-451)'
    next_retry_at: '2026-08-04T15:39:57.487455+00:00'
oompah.task_costs:
  total_input_tokens: 62
  total_output_tokens: 1584
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 62
      output_tokens: 1584
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 62
    output_tokens: 1584
    cost_usd: 0.0
    recorded_at: '2026-08-04T15:26:06.710860+00:00'
---
## Summary

Problem: OOMPAH-318 was merged to main at a4975ea71 before later child work completed. Six accepted child tasks are recorded as Merged, but the implementation commits remain only on origin/epic-OOMPAH-318. Current main lacks oompah/gitlab_tracker.py, GitLabHookManager, most GitLab webhook event parsing, and lifecycle wiring. The first live GitLab project exposed these gaps.

Scope: recover the still-required GitLab capabilities from commits 24ae25693, 696d5bfaa, 2b3312672, 4302b74e8, and 62cde900b by reconciling them selectively onto current main. Do not merge the stale epic branch wholesale because it is hundreds of commits behind and would revert unrelated current work. Include the project-editor regression discovered during live onboarding.

Tests: run focused tracker, webhook, project CRUD/UI, forge-isolation, lifecycle, and cross-forge acceptance suites, then make test.

Acceptance criteria: a GitLab managed project can be added, edited, state-branch enabled, polled, receive authenticated hooks, use GitLab Issues when configured, and exercise MR/pipeline workflows without invoking GitHub-only APIs or subprocesses; all recovered task state reflects code actually reachable from main.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 14:18
---
Closed premature PR #558 because this epic is not ready to merge while OOMPAH-456 remains in progress. Preserved epic-OOMPAH-451 for the remaining child work. OOMPAH-501/PR #559 prevents child close handoffs from creating a rollup review and rechecks the full epic readiness immediately before provider review creation; a fresh epic-owned PR will be created only after the entire branch is ready.
---
author: oompah
created: 2026-08-04 15:19
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 15:20
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 15:20
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 15:25
---
Needs Human — Archived audit requires operator input.

[REDACTED] Please review the audit output, decide the next step, and update this task with your instructions.
---
author: oompah
created: 2026-08-04 15:26
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 31
- Tokens: 62 in / 1.6K out [1.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 44s
- Log: OOMPAH-451__20260804T152035Z.jsonl
---
author: oompah
created: 2026-08-04 15:30
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 15:30
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 7s
---
author: oompah
created: 2026-08-04 15:30
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-451 (tried: origin/epic-OOMPAH-451, origin/OOMPAH-451). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 15:38
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 15:38
---
Run #2 [attempt=2, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 3s
---
author: oompah
created: 2026-08-04 15:38
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-451 (tried: origin/epic-OOMPAH-451, origin/OOMPAH-451). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 15:39
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-04 15:39
---
Run #3 [attempt=3, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 7s
---
author: oompah
created: 2026-08-04 15:39
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-451 (tried: origin/epic-OOMPAH-451, origin/OOMPAH-451). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 15:45
---
Needs Human — Done audit requires operator input.

Independent auditor launches exhausted their retry budget because the audit workspace or transport failed before review began. Restore the audit infrastructure, then have a project owner rearm this terminal audit; do not reopen implementation work.
---
<!-- COMMENTS:END -->
