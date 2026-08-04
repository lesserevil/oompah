---
id: OOMPAH-490
type: epic
status: In Validation
priority: 1
title: Prune redundant tests and isolate the suite from live infrastructure
parent: null
children:
- OOMPAH-491
- OOMPAH-492
- OOMPAH-493
- OOMPAH-494
- OOMPAH-495
- OOMPAH-496
- OOMPAH-497
- OOMPAH-498
- OOMPAH-499
- OOMPAH-500
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T13:51:11.052512Z'
updated_at: '2026-08-04T18:06:01.727814Z'
work_branch: epic-OOMPAH-490
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/563
review_number: '563'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/563
oompah.review_number: '563'
oompah.work_branch: epic-OOMPAH-490
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-4235dd76a811: '2026-08-04T17:57:31.777583+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-490
    target_state: Archived
    evidence_fingerprint: 3e3610fa43b469229d03dedf5959434f2861f2cb85d542b40502214cbe776f99
    audit_ids:
    - audit-05cb93465a95
    kind: result
    applied: true
    retired_at: '2026-08-04T17:57:31.777594+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-490
    audit_id: audit-05cb93465a95
    attempt_id: attempt-4235dd76a811
    target_state: Archived
    evidence_fingerprint: 3e3610fa43b469229d03dedf5959434f2861f2cb85d542b40502214cbe776f99
    status: In Validation
    audit_ids:
    - audit-05cb93465a95
    applied: true
    created_at: '2026-08-04T17:57:31.777609+00:00'
    applied_at: '2026-08-04T17:57:38.710214+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-05cb93465a95
    project_id: proj-14849f1b
    task_id: OOMPAH-490
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3e3610fa43b469229d03dedf5959434f2861f2cb85d542b40502214cbe776f99
    attempts:
    - version: 1
      attempt_id: attempt-4235dd76a811
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 3e3610fa43b469229d03dedf5959434f2861f2cb85d542b40502214cbe776f99
      created_at: '2026-08-04T17:52:47.841469+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T17:52:47.841469+00:00'
      branch_key: epic-OOMPAH-490
      verdict: pass
      completed_at: '2026-08-04T17:57:31.777382+00:00'
      ended_at: '2026-08-04T17:57:31.777382+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T17:25:37.057351+00:00'
    updated_at: '2026-08-04T17:57:31.777382+00:00'
  - version: 1
    audit_id: audit-801f3111cfd3
    project_id: proj-14849f1b
    task_id: OOMPAH-490
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b3ebbd825ceb8284c0daae2bdfe287fe0a0e42fe8992650b4137ffb0d1d32e2c
    attempts:
    - version: 1
      attempt_id: attempt-74fd51f376da
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b3ebbd825ceb8284c0daae2bdfe287fe0a0e42fe8992650b4137ffb0d1d32e2c
      created_at: '2026-08-04T17:57:59.615207+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T17:57:59.615207+00:00'
      branch_key: epic-OOMPAH-490
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T17:58:20.397357+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-490 (tried: origin/epic-OOMPAH-490, origin/OOMPAH-490)'
      next_retry_at: '2026-08-04T17:58:30.397319+00:00'
    - version: 1
      attempt_id: attempt-d1aa01e76599
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b3ebbd825ceb8284c0daae2bdfe287fe0a0e42fe8992650b4137ffb0d1d32e2c
      created_at: '2026-08-04T18:02:47.522687+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T18:02:47.522687+00:00'
      branch_key: epic-OOMPAH-490
      candidate_rotation_count: 1
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T18:03:02.371420+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-490 (tried: origin/epic-OOMPAH-490, origin/OOMPAH-490)'
      next_retry_at: '2026-08-04T18:03:22.371392+00:00'
    - version: 1
      attempt_id: attempt-68f0e3bab840
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b3ebbd825ceb8284c0daae2bdfe287fe0a0e42fe8992650b4137ffb0d1d32e2c
      created_at: '2026-08-04T18:05:48.668916+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-04T18:05:48.668916+00:00'
      branch_key: epic-OOMPAH-490
      candidate_rotation_count: 2
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T17:27:37.627571+00:00'
    updated_at: '2026-08-04T18:05:48.668916+00:00'
  - version: 1
    audit_id: audit-8170b4cbabb1
    project_id: proj-14849f1b
    task_id: OOMPAH-490
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b3ebbd825ceb8284c0daae2bdfe287fe0a0e42fe8992650b4137ffb0d1d32e2c
    attempts: []
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T17:27:37.627571+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-4235dd76a811
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3e3610fa43b469229d03dedf5959434f2861f2cb85d542b40502214cbe776f99
    created_at: '2026-08-04T17:52:47.841469+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T17:52:47.841469+00:00'
    branch_key: epic-OOMPAH-490
  - version: 1
    attempt_id: attempt-74fd51f376da
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b3ebbd825ceb8284c0daae2bdfe287fe0a0e42fe8992650b4137ffb0d1d32e2c
    created_at: '2026-08-04T17:57:59.615207+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T17:57:59.615207+00:00'
    branch_key: epic-OOMPAH-490
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T17:58:20.397357+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-490 (tried: origin/epic-OOMPAH-490, origin/OOMPAH-490)'
    next_retry_at: '2026-08-04T17:58:30.397319+00:00'
  - version: 1
    attempt_id: attempt-d1aa01e76599
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b3ebbd825ceb8284c0daae2bdfe287fe0a0e42fe8992650b4137ffb0d1d32e2c
    created_at: '2026-08-04T18:02:47.522687+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T18:02:47.522687+00:00'
    branch_key: epic-OOMPAH-490
    candidate_rotation_count: 1
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T18:03:02.371420+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-490 (tried: origin/epic-OOMPAH-490, origin/OOMPAH-490)'
    next_retry_at: '2026-08-04T18:03:22.371392+00:00'
  - version: 1
    attempt_id: attempt-68f0e3bab840
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b3ebbd825ceb8284c0daae2bdfe287fe0a0e42fe8992650b4137ffb0d1d32e2c
    created_at: '2026-08-04T18:05:48.668916+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-04T18:05:48.668916+00:00'
    branch_key: epic-OOMPAH-490
    candidate_rotation_count: 2
oompah.task_costs:
  total_input_tokens: 37
  total_output_tokens: 9274
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 37
      output_tokens: 9274
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 37
    output_tokens: 9274
    cost_usd: 0.0
    recorded_at: '2026-08-04T17:57:55.966575+00:00'
---
## Summary

Objective

Reduce the pytest suite's maintenance burden and runtime without weakening behavior coverage, and make the suite safe to run from a developer checkout. The July 28 audit found 282 test modules, about 201,700 test lines, and 12,347 collected cases. A timed run reached 5,954 passing tests in 309.78 seconds before it was stopped because improperly isolated tests invoked the checkout's real `git push origin HEAD:main`. The audit also found stale design-only tests, repeated removed-UI assertions, repeated Granian process startups, overlapping release-delivery page suites, exact duplicate assertions, and test definitions hidden by duplicate Python names.

Scope and constraints

First add a suite-wide barrier against outbound Git remotes. Then isolate known slow tests, consolidate subprocess scenarios, remove tests that exercise only test-authored constants or fixtures, and merge duplicate static UI contracts. Preserve separate backend/forge adapter contracts, MCP route policy cases that use different route data, and still-reachable release compatibility behavior. Do not change production behavior merely to make pruning easier. A child may remove a test only after identifying the surviving test that protects the same behavior.

Child task standard

Each child description identifies the files and retained contracts. Use focused pytest commands while developing and run `make test` when the safety and isolation prerequisites are present. Record before/after collected-case counts for the files changed. Any deliberately retained duplication must be explained in a short code comment only when the reason is not obvious from the test name.

Acceptance criteria

All children are complete; no test can contact or push to an HTTP(S), SSH, or git-protocol remote; local temporary bare-remotes still work; the full `make test` suite passes from a clean checkout; redundant cases are measurably reduced; and unique tracker, provider, compatibility, lifecycle, and failure-path coverage remains intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 17:04
---
YOLO: merged PR #563.
---
author: oompah
created: 2026-08-04 17:25
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 17:52
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 17:52
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 17:57
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 4b001b3a3 Merge pull request #563 from lesserevil/epic-OOMPAH-490
- merge_date: 2026-07-28 12:04:30 -0500
- age_days: 7
- merge_stat: 21 files changed, 1418 insertions(+), 2427 deletions(-)
- safety_barrier_test: tests/test_git_remote_safety.py (353 lines, OOMPAH-491)
- new_duplicate_guard: tests/test_duplicate_names.py (70 lines, OOMPAH-499)
- removed_design_tests: test_state_branch_design.py (-565), test_draft_epic_badge.py (-99), test_draft_epic_swimlane.py (-113), test_draft_swimlane_toggle.py (-94)
- children_archived: OOMPAH-495, 496, 497, 498, 499
- children_in_validation: OOMPAH-491, 492, 493, 494, 500
- child_commits_verified: 491:0af15d271, 492:e8e03d7d1, 493:7cdbba3d9, 494:14a319df7, 495:93fbea87d, 496:bba2829f0, 497:09b4fbee0, 498:b8571c21d, 499:3b75371d8
- reachable_from_main: yes (a681ec2fc..4b001b3a3 chain)
---
author: oompah
created: 2026-08-04 17:57
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 45, Tool calls: 31
- Tokens: 37 in / 9.3K out [9.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 5m 4s
- Log: OOMPAH-490__20260804T175259Z.jsonl
---
author: oompah
created: 2026-08-04 17:58
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 17:58
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 8s
---
author: oompah
created: 2026-08-04 17:58
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-490 (tried: origin/epic-OOMPAH-490, origin/OOMPAH-490). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 18:02
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 18:03
---
Run #2 [attempt=2, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 8s
---
author: oompah
created: 2026-08-04 18:03
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-490 (tried: origin/epic-OOMPAH-490, origin/OOMPAH-490). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 18:05
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-04 18:06
---
Run #3 [attempt=3, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 7s
---
<!-- COMMENTS:END -->
