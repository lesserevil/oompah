---
id: OOMPAH-1342
type: epic
status: Needs Human
priority: 1
title: Recover production service throughput and workflow progress
parent: null
children:
- OOMPAH-1343
- OOMPAH-1344
- OOMPAH-1345
- OOMPAH-1346
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-26T18:42:41.866488Z'
updated_at: '2026-08-27T17:19:26.940153Z'
work_branch: epic-OOMPAH-1342
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/957
review_number: '957'
review_head: c838c152de0ba072b527b6b07076cdcd61f03745
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: manual-service-recovery-20260826-epic
  request_fingerprint: 070158bda33ab0d0629239fafe161aeb566b706e18982b59d6073e52830bd282
oompah.lifecycle_revision: 4
oompah.review_url: https://github.com/lesserevil/oompah/pull/957
oompah.review_number: '957'
oompah.work_branch: epic-OOMPAH-1342
oompah.target_branch: main
oompah.review_head: c838c152de0ba072b527b6b07076cdcd61f03745
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-e19f7d1f2d16
    project_id: proj-14849f1b
    task_id: OOMPAH-1342
    digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
  - version: 1
    audit_id: audit-317deb859e7d
    project_id: proj-14849f1b
    task_id: OOMPAH-1342
    digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
  applied_result_attempts:
    '["proj-14849f1b","OOMPAH-1342","audit-e19f7d1f2d16","attempt-54c84dbabf84"]': '2026-08-27T17:10:14.823867+00:00'
    '["proj-14849f1b","OOMPAH-1342","audit-e19f7d1f2d16","attempt-b76002a449fd"]': '2026-08-27T17:18:58.731806+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1342
    target_state: Done
    evidence_fingerprint: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
    workflow_revision: 7088c4d3100c5c8660e950261aa8d55e7144382d8c1990b19383b04048b5cf62
    selected_ref: origin/main
    selected_sha: 08f21678e53149428695ba19d0602f9177c84fab
    landing_revision: c838c152de0ba072b527b6b07076cdcd61f03745
    audit_ids:
    - audit-e19f7d1f2d16
    kind: result
    applied: true
    retired_at: '2026-08-27T17:18:58.731821+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1342
    audit_id: audit-e19f7d1f2d16
    attempt_id: attempt-b76002a449fd
    target_state: Done
    evidence_fingerprint: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
    status: Needs Human
    audit_ids:
    - audit-e19f7d1f2d16
    kind: result
    applied: true
    created_at: '2026-08-27T17:18:58.731832+00:00'
    applied_at: '2026-08-27T17:19:08.041834+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-e19f7d1f2d16
    project_id: proj-14849f1b
    task_id: OOMPAH-1342
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
    attempts:
    - version: 1
      attempt_id: attempt-5fa847dac389
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
      created_at: '2026-08-27T16:46:45.022090+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-27T16:46:45.022090+00:00'
      branch_key: epic-OOMPAH-1342
      selected_ref: origin/main
      selected_sha: 08f21678e53149428695ba19d0602f9177c84fab
      landing_revision: c838c152de0ba072b527b6b07076cdcd61f03745
      failure_classification: policy_incompatibility
      ended_at: '2026-08-27T16:56:47.650658+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-27T16:56:57.650629+00:00'
    - version: 1
      attempt_id: attempt-54c84dbabf84
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
      created_at: '2026-08-27T16:58:50.049846+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-27T16:58:50.049846+00:00'
      branch_key: epic-OOMPAH-1342
      selected_ref: origin/main
      selected_sha: 08f21678e53149428695ba19d0602f9177c84fab
      landing_revision: c838c152de0ba072b527b6b07076cdcd61f03745
      candidate_rotation_count: 1
      verdict: fail
      failure_classification: infrastructure_error
      ended_at: '2026-08-27T17:10:14.823738+00:00'
      failure_reason: retry ceiling reached; verdict left pending
    - version: 1
      attempt_id: attempt-b76002a449fd
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
      created_at: '2026-08-27T17:12:51.621229+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-27T17:12:51.621229+00:00'
      branch_key: epic-OOMPAH-1342
      selected_ref: origin/main
      selected_sha: 08f21678e53149428695ba19d0602f9177c84fab
      landing_revision: c838c152de0ba072b527b6b07076cdcd61f03745
      candidate_rotation_count: 2
      verdict: needs_human
      failure_classification: infrastructure_error
      completed_at: '2026-08-27T17:18:58.731650+00:00'
      ended_at: '2026-08-27T17:18:58.731650+00:00'
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah
      source: orchestrator
    previous_state: In Progress
    created_at: '2026-08-27T16:34:53.776144+00:00'
    eligible_at: '2026-08-27T16:34:53.776144+00:00'
    selected_ref: origin/main
    selected_sha: 08f21678e53149428695ba19d0602f9177c84fab
    landing_revision: c838c152de0ba072b527b6b07076cdcd61f03745
    workflow_revision: 7088c4d3100c5c8660e950261aa8d55e7144382d8c1990b19383b04048b5cf62
    updated_at: '2026-08-27T17:18:58.731650+00:00'
  - version: 1
    audit_id: audit-317deb859e7d
    project_id: proj-14849f1b
    task_id: OOMPAH-1342
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah
      source: orchestrator
    previous_state: In Progress
    created_at: '2026-08-27T16:34:53.776144+00:00'
    prerequisite_audit_id: audit-e19f7d1f2d16
    selected_ref: origin/main
    selected_sha: 08f21678e53149428695ba19d0602f9177c84fab
    landing_revision: c838c152de0ba072b527b6b07076cdcd61f03745
    workflow_revision: 7088c4d3100c5c8660e950261aa8d55e7144382d8c1990b19383b04048b5cf62
  attempt_history:
  - version: 1
    attempt_id: attempt-5fa847dac389
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
    created_at: '2026-08-27T16:46:45.022090+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-27T16:46:45.022090+00:00'
    branch_key: epic-OOMPAH-1342
    selected_ref: origin/main
    selected_sha: 08f21678e53149428695ba19d0602f9177c84fab
    landing_revision: c838c152de0ba072b527b6b07076cdcd61f03745
    failure_classification: policy_incompatibility
    ended_at: '2026-08-27T16:56:47.650658+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-27T16:56:57.650629+00:00'
  - version: 1
    attempt_id: attempt-54c84dbabf84
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
    created_at: '2026-08-27T16:58:50.049846+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-27T16:58:50.049846+00:00'
    branch_key: epic-OOMPAH-1342
    selected_ref: origin/main
    selected_sha: 08f21678e53149428695ba19d0602f9177c84fab
    landing_revision: c838c152de0ba072b527b6b07076cdcd61f03745
    candidate_rotation_count: 1
  - version: 1
    attempt_id: attempt-b76002a449fd
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 7770ca18ce34d7d40f3ded77ee64eb779eb526edd15c61a2bbf2ae48784acf01
    created_at: '2026-08-27T17:12:51.621229+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-27T17:12:51.621229+00:00'
    branch_key: epic-OOMPAH-1342
    selected_ref: origin/main
    selected_sha: 08f21678e53149428695ba19d0602f9177c84fab
    landing_revision: c838c152de0ba072b527b6b07076cdcd61f03745
    candidate_rotation_count: 2
oompah.task_costs:
  total_input_tokens: 727
  total_output_tokens: 25037
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 727
      output_tokens: 25037
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 678
    output_tokens: 171
    cost_usd: 0.0
    recorded_at: '2026-08-27T16:57:00.183883+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 22
    output_tokens: 10017
    cost_usd: 0.0
    recorded_at: '2026-08-27T17:10:30.560423+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 27
    output_tokens: 14849
    cost_usd: 0.0
    recorded_at: '2026-08-27T17:19:23.853579+00:00'
---
## Summary

Implement the accepted recovery plan in plans/service-throughput-recovery.md. This epic coordinates four independently deliverable children: deployment stabilization, bounded reconciliation/forge observations, snapshot-backed reviews API, and bounded storage retention. Preserve fail-closed lifecycle, exact-head, project-scope, and audit guarantees. Require focused tests for every child and the complete Makefile gate plus workflow rollout check before resuming production projects. Acceptance: the children are complete in rollout order, production reconciliation stays inside its configured budget, APIs remain responsive, storage growth is bounded, exhausted decisions have explicit dispositions, and projects resume without unexplained liveness divergence.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-26 22:50
---
Recovery implementation is pushed on epic-OOMPAH-1342 and PR #951. Full make test passes: 20,449 passed, 7 skipped, 2 xfailed. Production remains globally paused; storage reclaimed from 93% to 79% used, and /api/v1/reviews dropped from >20s timeout to ~0.08s on the deployed candidate.
---
author: oompah
created: 2026-08-26 23:36
---
Progress update: PR #951 merged to main at 13718ac1c after GitHub CI passed. Focused suites pass (756) and the full local gate passes (20,449 passed, 7 skipped, 2 xfailed). Production is deployed on that revision and remains globally paused. Disk pressure was relieved from 93% to 79%; the reviews endpoint returns from memory in under 0.1s. Remaining controlled work is production re-enable/canary and explicit disposition of historical exhausted jobs.
---
author: oompah
created: 2026-08-27 03:16
---
Progress: deployed PR #959 at 08f21678e. Oompah-only complete reconciliation improved to 129.545s (implementation 3.146s, review 11.399s, integration 106.101s, epic 7.941s) with complete recovery, zero current divergence, zero source errors, and zero action-required decisions. This remains 9.545s above the 120s convergence budget, so global and all project pauses were restored. Continuing to remove remaining per-revision forge I/O under direct human control.
---
author: oompah
created: 2026-08-27 04:03
---
Queue hygiene cleanup completed under global/project pause. Closed all 8 stale conflicting Oompah PRs (#939, #947-950, #954-955, #960), archived their 11 superseded tasks with owner override, and deleted their remote branches. Archived another 44 duplicate auto-filed contributor-evidence/worker-dispatch tasks that were still Ready to Integrate despite the root fixes already being on main. Closed 8 stale blocked Trickle draft MRs (!3, !10-13, !16-18), archived their tasks with explicit fresh-revision requirements, and deleted their remote branches. Review inventory fell from 21 to 6 and conflict count from 11 to 0; Ready to Integrate fell from 77 to 32 (Oompah 49 to 5). Remaining six Trickle MRs are non-draft and conflict-free; their CI/blocker disposition remains to be handled separately.
---
author: oompah
created: 2026-08-27 15:27
---
Trickle review audit: six non-draft MRs remain and none conflicts. MR !7/TRICKLE-119 and !19/TRICKLE-121 were already green; retried the exact failed macOS jobs for !8/TRICKLE-120 and !14/TRICKLE-136 and both now pass, making those MRs mergeable. !15/TRICKLE-135 and !20/TRICKLE-143 still fail deterministically in ci:test-macos because sccache reports 2,553 compiler cache errors; these need an actual branch fix, not another retry. Removed the untracked .oompah-no-hooks helpers from the four integration worktrees and resubmitted exact remote heads for TRICKLE-119/120/135/136. Automatic lifecycle advancement is not currently occurring because the service and Trickle remain paused for recovery validation.
---
author: oompah
created: 2026-08-27 15:58
---
Service resumed with Oompah and Trickle enabled; Exocomp remains paused. After convergence, the latest full two-project reconciliation completed in 57.900s (Oompah integration 28.122s; Trickle integration 7.296s), inside the 120s budget. Workflow liveness is healthy, complete 27/27, with zero divergence, zero action-required decisions, and no source errors. Trickle MRs !7, !8, !14, and !19 are green/mergeable. MRs !15 and !20 remain blocked by reproducible macOS sccache health failures and need implementation repair. Generated worktree helpers were removed and exact heads resubmitted for TRICKLE-119/120/135/136/142.
---
author: oompah
created: 2026-08-27 16:35
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-27 16:37
---
Service resumed per operator request with Oompah and Trickle enabled; Exocomp remains paused. After initial correction churn, a full two-project generation completed in 57.900s, liveness healthy/complete 27/27, zero divergence/action-required/source errors. Current service remains unpaused and healthy enough to schedule. Separately, scoped Pi-provider design work is being captured in plans/ without creating implementation tasks until accepted.
---
author: oompah
created: 2026-08-27 16:46
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-27 16:46
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-27 16:57
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-27 16:57
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/haiku]
- Turns: 0, Tool calls: 34
- Tokens: 678 in / 171 out [849 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 12s
- Log: OOMPAH-1342__20260827T164709Z.jsonl
---
author: oompah
created: 2026-08-27 16:58
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-27 16:59
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-27 17:10
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 55, Tool calls: 28
- Tokens: 22 in / 10.0K out [10.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 11m 37s
- Log: OOMPAH-1342__20260827T165911Z.jsonl
---
author: oompah
created: 2026-08-27 17:12
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-27 17:13
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-27 17:19
---
Needs Human — Done audit requires operator input.

[REDACTED]

Instructions:
- Run `make test` from the service checkout (or a worktree whose OOMPAH_SERVICE_CHECKOUT marker matches the Git-derived primary) at exactly SHA 08f21678e and record the passing result so the audit scheduler sees exact-head full-gate evidence.
- If the audit worktree layout cannot produce that evidence, adjust the auditor sandbox OOMPAH_SERVICE_CHECKOUT so it resolves to the same primary as the Git common directory, then redispatch the audit.
- Optionally attach a workflow-rollout-check result for the current head; the plan calls for it before resuming production but it is not a substitute for the full make test gate.
---
author: oompah
created: 2026-08-27 17:19
---
Run #3 [attempt=3, profile=auditor, role=auditor -> Claude/opus]
- Turns: 44, Tool calls: 28
- Tokens: 27 in / 14.8K out [14.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 29s
- Log: OOMPAH-1342__20260827T171315Z.jsonl
---
<!-- COMMENTS:END -->
