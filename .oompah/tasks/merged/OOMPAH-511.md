---
id: OOMPAH-511
type: epic
status: Merged
priority: 1
title: Prevent managed task writes from bypassing state branches
parent: null
children:
- OOMPAH-512
- OOMPAH-513
- OOMPAH-514
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T15:16:09.831740Z'
updated_at: '2026-08-04T16:58:46.538032Z'
work_branch: epic-OOMPAH-511
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/562
review_number: '562'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/562
oompah.review_number: '562'
oompah.work_branch: epic-OOMPAH-511
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-cb96d0a8036a: '2026-08-04T16:32:06.464468+00:00'
    infrastructure-exhausted-audit-6fabd90c6453-3: '2026-08-04T16:47:27.615730+00:00'
    attempt-4f96a4a34465: '2026-08-04T16:58:00.191628+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-511
    target_state: Archived
    evidence_fingerprint: d46f59de6b7e98be6b90abb05ad71e10fedea7b02363822c30dd5c37750f1529
    audit_ids:
    - audit-dc2b7e9fa81f
    kind: result
    applied: true
    retired_at: '2026-08-04T16:32:06.464480+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-511
    target_state: Done
    evidence_fingerprint: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    audit_ids:
    - audit-6fabd90c6453
    kind: result
    applied: true
    retired_at: '2026-08-04T16:47:27.615747+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-511
    target_state: Merged
    evidence_fingerprint: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    audit_ids:
    - audit-35731bc0bd87
    kind: result
    applied: true
    retired_at: '2026-08-04T16:58:00.191646+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-511
    audit_id: audit-dc2b7e9fa81f
    attempt_id: attempt-cb96d0a8036a
    target_state: Archived
    evidence_fingerprint: d46f59de6b7e98be6b90abb05ad71e10fedea7b02363822c30dd5c37750f1529
    status: In Validation
    audit_ids:
    - audit-dc2b7e9fa81f
    applied: true
    created_at: '2026-08-04T16:32:06.464497+00:00'
    applied_at: '2026-08-04T16:32:16.301930+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-511
    audit_id: audit-6fabd90c6453
    attempt_id: infrastructure-exhausted-audit-6fabd90c6453-3
    target_state: Done
    evidence_fingerprint: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    status: Needs Human
    audit_ids:
    - audit-6fabd90c6453
    applied: true
    created_at: '2026-08-04T16:47:27.615766+00:00'
    applied_at: '2026-08-04T16:47:34.760844+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-511
    audit_id: audit-35731bc0bd87
    attempt_id: attempt-4f96a4a34465
    target_state: Merged
    evidence_fingerprint: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    status: Merged
    audit_ids:
    - audit-35731bc0bd87
    applied: true
    created_at: '2026-08-04T16:58:00.191667+00:00'
    applied_at: '2026-08-04T16:58:08.695929+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-dc2b7e9fa81f
    project_id: proj-14849f1b
    task_id: OOMPAH-511
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d46f59de6b7e98be6b90abb05ad71e10fedea7b02363822c30dd5c37750f1529
    attempts:
    - version: 1
      attempt_id: attempt-cb96d0a8036a
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d46f59de6b7e98be6b90abb05ad71e10fedea7b02363822c30dd5c37750f1529
      created_at: '2026-08-04T16:26:01.168349+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T16:26:01.168349+00:00'
      branch_key: epic-OOMPAH-511
      verdict: pass
      completed_at: '2026-08-04T16:32:06.464292+00:00'
      ended_at: '2026-08-04T16:32:06.464292+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T16:24:35.836414+00:00'
    updated_at: '2026-08-04T16:32:06.464292+00:00'
  - version: 1
    audit_id: audit-6fabd90c6453
    project_id: proj-14849f1b
    task_id: OOMPAH-511
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    attempts:
    - version: 1
      attempt_id: attempt-ea5e085db1ce
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
      created_at: '2026-08-04T16:32:59.944603+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T16:32:59.944603+00:00'
      branch_key: epic-OOMPAH-511
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T16:33:13.293305+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-511 (tried: origin/epic-OOMPAH-511, origin/OOMPAH-511)'
      next_retry_at: '2026-08-04T16:33:23.293270+00:00'
    - version: 1
      attempt_id: attempt-0b79ccc027fe
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
      created_at: '2026-08-04T16:38:06.030864+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T16:38:06.030864+00:00'
      branch_key: epic-OOMPAH-511
      candidate_rotation_count: 1
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T16:38:20.402685+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-511 (tried: origin/epic-OOMPAH-511, origin/OOMPAH-511)'
      next_retry_at: '2026-08-04T16:38:40.402658+00:00'
    - version: 1
      attempt_id: attempt-e164f7f98515
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
      created_at: '2026-08-04T16:43:55.158887+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-04T16:43:55.158887+00:00'
      branch_key: epic-OOMPAH-511
      candidate_rotation_count: 2
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T16:44:03.282621+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-511 (tried: origin/epic-OOMPAH-511, origin/OOMPAH-511)'
      next_retry_at: '2026-08-04T16:44:43.282592+00:00'
    - version: 1
      attempt_id: infrastructure-exhausted-audit-6fabd90c6453-3
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
      verdict: needs_human
      failure_classification: infrastructure_error
      created_at: '2026-08-04T16:47:27.615614+00:00'
      completed_at: '2026-08-04T16:47:27.615614+00:00'
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T16:25:26.662298+00:00'
    updated_at: '2026-08-04T16:47:27.615614+00:00'
  - version: 1
    audit_id: audit-35731bc0bd87
    project_id: proj-14849f1b
    task_id: OOMPAH-511
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    attempts:
    - version: 1
      attempt_id: attempt-4f96a4a34465
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
      created_at: '2026-08-04T16:50:05.374531+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T16:50:05.374531+00:00'
      branch_key: epic-OOMPAH-511
      verdict: pass
      completed_at: '2026-08-04T16:58:00.191411+00:00'
      ended_at: '2026-08-04T16:58:00.191411+00:00'
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T16:25:26.662298+00:00'
    updated_at: '2026-08-04T16:58:00.191411+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-cb96d0a8036a
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d46f59de6b7e98be6b90abb05ad71e10fedea7b02363822c30dd5c37750f1529
    created_at: '2026-08-04T16:26:01.168349+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T16:26:01.168349+00:00'
    branch_key: epic-OOMPAH-511
  - version: 1
    attempt_id: attempt-ea5e085db1ce
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    created_at: '2026-08-04T16:32:59.944603+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T16:32:59.944603+00:00'
    branch_key: epic-OOMPAH-511
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T16:33:13.293305+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-511 (tried: origin/epic-OOMPAH-511, origin/OOMPAH-511)'
    next_retry_at: '2026-08-04T16:33:23.293270+00:00'
  - version: 1
    attempt_id: attempt-0b79ccc027fe
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    created_at: '2026-08-04T16:38:06.030864+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T16:38:06.030864+00:00'
    branch_key: epic-OOMPAH-511
    candidate_rotation_count: 1
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T16:38:20.402685+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-511 (tried: origin/epic-OOMPAH-511, origin/OOMPAH-511)'
    next_retry_at: '2026-08-04T16:38:40.402658+00:00'
  - version: 1
    attempt_id: attempt-e164f7f98515
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    created_at: '2026-08-04T16:43:55.158887+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-04T16:43:55.158887+00:00'
    branch_key: epic-OOMPAH-511
    candidate_rotation_count: 2
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T16:44:03.282621+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-511 (tried: origin/epic-OOMPAH-511, origin/OOMPAH-511)'
    next_retry_at: '2026-08-04T16:44:43.282592+00:00'
  - version: 1
    attempt_id: attempt-4f96a4a34465
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e71dfa7416a52cb6bc6b3a4d8a9dd8360dcefdcdf3bd14817ceea24fdb92b6c4
    created_at: '2026-08-04T16:50:05.374531+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T16:50:05.374531+00:00'
    branch_key: epic-OOMPAH-511
oompah.task_costs:
  total_input_tokens: 103
  total_output_tokens: 17053
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 103
      output_tokens: 17053
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 45
    output_tokens: 8447
    cost_usd: 0.0
    recorded_at: '2026-08-04T16:32:43.897811+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 58
    output_tokens: 8606
    cost_usd: 0.0
    recorded_at: '2026-08-04T16:58:43.952703+00:00'
---
## Summary

Problem

A managed Oompah project can be configured to keep native Markdown task state on a dedicated Git state branch, yet legacy/global tracker consumers still construct a writable OompahMarkdownTracker from the server process working directory. When background maintenance or another unscoped consumer uses that tracker, task and epic updates are committed directly to the code checkout and can be pushed to the default branch, bypassing the project's designated state branch.

Scope

Make project-scoped tracker resolution mandatory for managed-project writes, prevent an unscoped legacy tracker from mutating a registered state-branch project, and add end-to-end protection proving maintenance and server-side consumers cannot change the code branch. Preserve standalone/single-repository compatibility where no managed project store is configured. Coordinate with, but do not duplicate, OOMPAH-492's targeted worker-exit and epic-rebase test isolation.

Relevant code includes oompah/orchestrator.py, oompah/server.py, oompah/oompah_md_tracker.py, background maintenance consumers, and tracker-oriented tests. All configuration remains in .env; no WORKFLOW.md tuning.

Acceptance criteria

All native task writes for a state-branch-enabled managed project resolve through that project's configured tracker; an unscoped/default-branch write attempt fails before modifying Git; background maintenance and server helper paths cannot fall back to the process checkout; standalone compatibility is retained; focused tests and make test pass; and ordinary main/release histories receive no task metadata commits.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:17
---
Claimed for this manual implementation session. Work will be completed sequentially in an isolated epic-OOMPAH-511 worktree; OOMPAH-492 remains with its existing worker because its targeted test isolation is complementary, not duplicated.
---
author: oompah
created: 2026-07-28 15:42
---
Implementation complete and pushed at 6533e235e. All three child tasks are Done and the complete epic branch is ready for review in https://github.com/lesserevil/oompah/pull/562. Validation: 12,402 tests passed, 39 skipped; secret scan passed; worktree is clean and synchronized with origin.
---
author: oompah
created: 2026-07-28 15:47
---
GitHub CI is green on Python 3.11, 3.12, and 3.13 for PR #562. The epic has no remaining implementation or test blocker; it is awaiting review/merge.
---
author: oompah
created: 2026-07-28 16:23
---
YOLO: merged PR #562.
---
author: oompah
created: 2026-08-04 16:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 16:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 16:26
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 16:32
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 1143e5cb139b795262ff0e7d0cbd3753751940f7
- epic_impl_commit: 6533e235e
- coverage_commit: 5397b7a82
- pull_request: https://github.com/lesserevil/oompah/pull/562
- days_since_merge: 7
- merged_into_main: true
- regression_test_file: tests/test_managed_tracker_state_branch_guard.py
- regression_test_size_lines: 535
- children: OOMPAH-512, OOMPAH-513, OOMPAH-514
- task_file_location: oompah/state/proj-14849f1b:.oompah/tasks/in-validation/OOMPAH-511.md
- worktree_status: clean
---
author: oompah
created: 2026-08-04 16:32
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 52, Tool calls: 39
- Tokens: 45 in / 8.4K out [8.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 38s
- Log: OOMPAH-511__20260804T162616Z.jsonl
---
author: oompah
created: 2026-08-04 16:33
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 16:33
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 6s
---
author: oompah
created: 2026-08-04 16:33
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-511 (tried: origin/epic-OOMPAH-511, origin/OOMPAH-511). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 16:38
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 16:38
---
Run #2 [attempt=2, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 6s
---
author: oompah
created: 2026-08-04 16:38
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-511 (tried: origin/epic-OOMPAH-511, origin/OOMPAH-511). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 16:43
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-04 16:44
---
Run #3 [attempt=3, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 4s
---
author: oompah
created: 2026-08-04 16:44
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-511 (tried: origin/epic-OOMPAH-511, origin/OOMPAH-511). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 16:47
---
Needs Human — Done audit requires operator input.

Independent auditor launches exhausted their retry budget because the audit workspace or transport failed before review began. Restore the audit infrastructure, then have a project owner rearm this terminal audit; do not reopen implementation work.
---
author: oompah
created: 2026-08-04 16:50
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 16:50
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 16:58
---
Audit PASS — Merged

Merge, implementation, and coverage commits are all reachable from origin/main; the epic guard, tracker constructor plumbing, and the regression suite are all present, and the focused test suites confirm the guarded write path still fails closed while state-branch and shadow-write paths remain writable.

Safe evidence:
- merge_commit: 1143e5cb139b795262ff0e7d0cbd3753751940f7
- epic_impl_commit: 6533e235e262d76334032d4aa8c5d5865b75acb2
- coverage_commit: 5397b7a827c48c0e
- merge_ancestor_of_origin_main: true
- impl_ancestor_of_main: true
- coverage_ancestor_of_main: true
- main_head: a681ec2fc005f339063b3b8e2a139b8ae0b3c379
- origin_main_head: a681ec2fc005f339063b3b8e2a139b8ae0b3c379
- regression_test_file: tests/test_managed_tracker_state_branch_guard.py
- regression_test_test_functions: 9
- guard_symbol_source: oompah/oompah_md_tracker.py:_assert_task_writes_allowed
- guard_constructor_flag: allow_default_branch_task_writes
- orchestrator_flag_plumbing_lines: 3674,3756
- focused_tests_run: tests/test_managed_tracker_state_branch_guard.py,tests/test_oompah_md_tracker_state_branch.py,tests/test_epic_draft_migration.py
- focused_tests_result: 67 passed (19 + 34 + 14)
- worktree_status: clean
- pull_request: https://github.com/lesserevil/oompah/pull/562
---
author: oompah
created: 2026-08-04 16:58
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 52
- Tokens: 58 in / 8.6K out [8.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 34s
- Log: OOMPAH-511__20260804T165022Z.jsonl
---
<!-- COMMENTS:END -->
