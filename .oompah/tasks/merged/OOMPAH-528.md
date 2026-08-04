---
id: OOMPAH-528
type: epic
status: Merged
priority: 2
title: Pre-dispatch duplicate screening for Open tasks
parent: null
children:
- OOMPAH-529
- OOMPAH-530
- OOMPAH-531
- OOMPAH-532
- OOMPAH-533
- OOMPAH-534
blocked_by: []
labels:
- epic:stale
assignee: null
created_at: '2026-07-28T21:18:12.111324Z'
updated_at: '2026-08-04T23:58:17.152536Z'
work_branch: epic-OOMPAH-528
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/568
review_number: '568'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/568
oompah.review_number: '568'
oompah.work_branch: epic-OOMPAH-528
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-a705eeb8efb0: '2026-08-04T23:18:23.346935+00:00'
    infrastructure-exhausted-audit-dde088fa5610-3: '2026-08-04T23:45:18.828829+00:00'
    attempt-64f11c571883: '2026-08-04T23:58:13.596665+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-528
    target_state: Archived
    evidence_fingerprint: 76133fc83b06b40ae63cc8cc81948a6b5e3c3df59f90b3383af8ccd8ed516c55
    audit_ids:
    - audit-43da28b812da
    kind: result
    applied: true
    retired_at: '2026-08-04T23:18:23.346947+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-528
    target_state: Done
    evidence_fingerprint: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    audit_ids:
    - audit-dde088fa5610
    kind: result
    applied: true
    retired_at: '2026-08-04T23:45:18.828845+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-528
    target_state: Merged
    evidence_fingerprint: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    audit_ids:
    - audit-a45d3bca4588
    kind: result
    applied: true
    retired_at: '2026-08-04T23:58:13.596684+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-528
    audit_id: audit-43da28b812da
    attempt_id: attempt-a705eeb8efb0
    target_state: Archived
    evidence_fingerprint: 76133fc83b06b40ae63cc8cc81948a6b5e3c3df59f90b3383af8ccd8ed516c55
    status: In Validation
    audit_ids:
    - audit-43da28b812da
    applied: true
    created_at: '2026-08-04T23:18:23.346964+00:00'
    applied_at: '2026-08-04T23:18:30.761094+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-528
    audit_id: audit-dde088fa5610
    attempt_id: infrastructure-exhausted-audit-dde088fa5610-3
    target_state: Done
    evidence_fingerprint: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    status: Needs Human
    audit_ids:
    - audit-dde088fa5610
    applied: true
    created_at: '2026-08-04T23:45:18.828861+00:00'
    applied_at: '2026-08-04T23:45:26.497495+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-528
    audit_id: audit-a45d3bca4588
    attempt_id: attempt-64f11c571883
    target_state: Merged
    evidence_fingerprint: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    status: Merged
    audit_ids:
    - audit-a45d3bca4588
    applied: false
    created_at: '2026-08-04T23:58:13.596707+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-43da28b812da
    project_id: proj-14849f1b
    task_id: OOMPAH-528
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 76133fc83b06b40ae63cc8cc81948a6b5e3c3df59f90b3383af8ccd8ed516c55
    attempts:
    - version: 1
      attempt_id: attempt-a705eeb8efb0
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 76133fc83b06b40ae63cc8cc81948a6b5e3c3df59f90b3383af8ccd8ed516c55
      created_at: '2026-08-04T23:12:12.003450+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T23:12:12.003450+00:00'
      branch_key: epic-OOMPAH-528
      verdict: pass
      completed_at: '2026-08-04T23:18:23.346770+00:00'
      ended_at: '2026-08-04T23:18:23.346770+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T22:36:13.665152+00:00'
    updated_at: '2026-08-04T23:18:23.346770+00:00'
  - version: 1
    audit_id: audit-dde088fa5610
    project_id: proj-14849f1b
    task_id: OOMPAH-528
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    attempts:
    - version: 1
      attempt_id: attempt-fc912c848810
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
      created_at: '2026-08-04T23:21:23.861824+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T23:21:23.861824+00:00'
      branch_key: epic-OOMPAH-528
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T23:21:38.520433+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-528 (tried: origin/epic-OOMPAH-528, origin/OOMPAH-528)'
      next_retry_at: '2026-08-04T23:21:48.520400+00:00'
    - version: 1
      attempt_id: attempt-f3cafad48c30
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
      created_at: '2026-08-04T23:33:05.066881+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-04T23:33:05.066881+00:00'
      branch_key: epic-OOMPAH-528
      candidate_rotation_count: 1
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T23:33:29.503265+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-528 (tried: origin/epic-OOMPAH-528, origin/OOMPAH-528)'
      next_retry_at: '2026-08-04T23:33:49.503230+00:00'
    - version: 1
      attempt_id: attempt-7882f5ab30ee
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
      created_at: '2026-08-04T23:42:33.450901+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-04T23:42:33.450901+00:00'
      branch_key: epic-OOMPAH-528
      candidate_rotation_count: 2
      failure_classification: infrastructure_error
      ended_at: '2026-08-04T23:42:43.868361+00:00'
      failure_reason: 'terminal audit evidence has no safely resolvable revision for
        OOMPAH-528 (tried: origin/epic-OOMPAH-528, origin/OOMPAH-528)'
      next_retry_at: '2026-08-04T23:43:23.868332+00:00'
    - version: 1
      attempt_id: infrastructure-exhausted-audit-dde088fa5610-3
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
      verdict: needs_human
      failure_classification: infrastructure_error
      created_at: '2026-08-04T23:45:18.828725+00:00'
      completed_at: '2026-08-04T23:45:18.828725+00:00'
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T22:37:37.756901+00:00'
    updated_at: '2026-08-04T23:45:18.828725+00:00'
  - version: 1
    audit_id: audit-a45d3bca4588
    project_id: proj-14849f1b
    task_id: OOMPAH-528
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    attempts:
    - version: 1
      attempt_id: attempt-64f11c571883
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
      created_at: '2026-08-04T23:53:15.690825+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T23:53:15.690825+00:00'
      branch_key: epic-OOMPAH-528
      verdict: pass
      completed_at: '2026-08-04T23:58:13.596475+00:00'
      ended_at: '2026-08-04T23:58:13.596475+00:00'
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Validation
    created_at: '2026-08-04T22:37:37.756901+00:00'
    updated_at: '2026-08-04T23:58:13.596475+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-a705eeb8efb0
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 76133fc83b06b40ae63cc8cc81948a6b5e3c3df59f90b3383af8ccd8ed516c55
    created_at: '2026-08-04T23:12:12.003450+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T23:12:12.003450+00:00'
    branch_key: epic-OOMPAH-528
  - version: 1
    attempt_id: attempt-fc912c848810
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    created_at: '2026-08-04T23:21:23.861824+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T23:21:23.861824+00:00'
    branch_key: epic-OOMPAH-528
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T23:21:38.520433+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-528 (tried: origin/epic-OOMPAH-528, origin/OOMPAH-528)'
    next_retry_at: '2026-08-04T23:21:48.520400+00:00'
  - version: 1
    attempt_id: attempt-f3cafad48c30
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    created_at: '2026-08-04T23:33:05.066881+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-04T23:33:05.066881+00:00'
    branch_key: epic-OOMPAH-528
    candidate_rotation_count: 1
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T23:33:29.503265+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-528 (tried: origin/epic-OOMPAH-528, origin/OOMPAH-528)'
    next_retry_at: '2026-08-04T23:33:49.503230+00:00'
  - version: 1
    attempt_id: attempt-7882f5ab30ee
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    created_at: '2026-08-04T23:42:33.450901+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-04T23:42:33.450901+00:00'
    branch_key: epic-OOMPAH-528
    candidate_rotation_count: 2
    failure_classification: infrastructure_error
    ended_at: '2026-08-04T23:42:43.868361+00:00'
    failure_reason: 'terminal audit evidence has no safely resolvable revision for
      OOMPAH-528 (tried: origin/epic-OOMPAH-528, origin/OOMPAH-528)'
    next_retry_at: '2026-08-04T23:43:23.868332+00:00'
  - version: 1
    attempt_id: attempt-64f11c571883
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e281ecd2c5582a00d1246aa72f4437b2b68c48f071b713b91597af9b7f6093d6
    created_at: '2026-08-04T23:53:15.690825+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T23:53:15.690825+00:00'
    branch_key: epic-OOMPAH-528
oompah.task_costs:
  total_input_tokens: 22
  total_output_tokens: 4128
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 22
      output_tokens: 4128
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 22
    output_tokens: 4128
    cost_usd: 0.0
    recorded_at: '2026-08-04T23:19:08.656650+00:00'
---
## Summary

Implement model-backed duplicate screening as a qualification stage that can prepare Open tasks before an implementation agent claims them.

Current behavior:
- The inexpensive similarity filter already scans non-terminal candidates before dispatch.
- The model-backed duplicate_detector is a normal focus run: it moves a task to In Progress and records focus-complete:duplicate_detector after handoff.
- That label is not tied to the task revision, so a material edit can leave stale screening evidence.

Target behavior:
- Open tasks without a current duplicate-screening result may use otherwise-available agent capacity for a model-backed preflight run.
- A preflight run uses a separate atomic claim and does not represent implementation work; the task remains Open and exposes screening state separately.
- A real implementation agent cannot claim the task while screening is running or while the result is missing/stale.
- A no-duplicate verdict persists revision-aware evidence and returns the task to implementation eligibility.
- A supported duplicate verdict moves the task to Duplicate Candidate and posts evidence linking the match.
- Screening compares only against non-terminal tasks.
- Task edits or detector-version changes invalidate old evidence automatically.
- Preflight work is capacity-capped so it cannot monopolize all configured agents.

Non-goals:
- Do not replace the existing inexpensive similarity filter.
- Do not change terminal-state definitions or include terminal tasks in duplicate comparisons.
- Do not treat a heuristic similarity miss as equivalent to a model-backed pass.

Acceptance criteria:
1. The complete child-task dependency graph is implemented and covered by tests.
2. Open tasks visibly progress through unchecked, running, checked, or stale duplicate-screening states without entering In Progress for screening alone.
3. Claims prevent preflight and implementation agents from running concurrently on the same task.
4. Screening evidence is portable across supported trackers and invalidates after relevant task changes.
5. Capacity behavior uses only allowed slots and preserves an implementation lane.
6. make test passes, documentation describes configuration and operator-visible behavior, and all work is committed and pushed on the epic branch.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:20
---
Claimed for implementation by the current interactive Codex session at the project owner's request. Oompah dispatch was paused before task creation; child tasks are dependency-ordered and will be claimed by this session before each predecessor is completed.
---
author: oompah
created: 2026-07-28 21:54
---
All six children are complete on epic-OOMPAH-528 at c4c7f5dfa, rebased onto origin/main e9681a58d. The branch provides revision-aware screening evidence, atomic claims and recovery, spare-capacity scheduling, verified verdict transitions, safe API/dashboard state, and operator documentation. Final full quality gate after rebase: 13,070 passed, 7 skipped. The project is intentionally paused until the completed epic branch is handed to the single final review/merge workflow.
---
author: oompah
created: 2026-07-28 21:54
---
Completed pre-dispatch duplicate screening across persistence, scheduling, verdict handling, visibility, tests, and documentation.
---
author: oompah
created: 2026-07-28 21:56
---
Branch quality gate passed for `92aa5e5c2410a0d69ec0e48c8ebfeef97f9516a2` using `make test` in 73.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-04 22:36
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 23:12
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 23:12
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 23:18
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 70771b4e9f27cf454bd628c71d2ef957585fe033
- merge_date: 2026-07-28 17:02:45 -0500
- pr_number: #568
- main_head: e1b0f4846054bacac48e667295e2c00733d86d8c
- merge_ancestor_of_main: true
- core_files_present_on_main: oompah/duplicate_screening.py, docs/duplicate-screening.md, tests/test_duplicate_screening.py, tests/test_duplicate_preflight.py, tests/test_dashboard_duplicate_screening.py
- later_maintenance_commits: OOMPAH-706 (0b78028a6), OOMPAH-682 (71f87859f, d11354931)
- days_since_merge: 7
---
author: oompah
created: 2026-08-04 23:19
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 23, Tool calls: 16
- Tokens: 22 in / 4.1K out [4.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 55s
- Log: OOMPAH-528__20260804T231226Z.jsonl
---
author: oompah
created: 2026-08-04 23:21
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 23:21
---
Run #1 [attempt=1, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 9s
---
author: oompah
created: 2026-08-04 23:21
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-528 (tried: origin/epic-OOMPAH-528, origin/OOMPAH-528). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 23:33
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-04 23:33
---
Run #2 [attempt=2, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 9s
---
author: oompah
created: 2026-08-04 23:33
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-528 (tried: origin/epic-OOMPAH-528, origin/OOMPAH-528). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 23:42
---
Auditor dispatched (attempt #3, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-04 23:42
---
Run #3 [attempt=3, profile=auditor, role=— -> unknown/unknown]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 6s
---
author: oompah
created: 2026-08-04 23:42
---
Auditor attempt ended: terminal audit evidence has no safely resolvable revision for OOMPAH-528 (tried: origin/epic-OOMPAH-528, origin/OOMPAH-528). A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-08-04 23:45
---
Needs Human — Done audit requires operator input.

Independent auditor launches exhausted their retry budget because the audit workspace or transport failed before review began. Restore the audit infrastructure, then have a project owner rearm this terminal audit; do not reopen implementation work.
---
author: oompah
created: 2026-08-04 23:53
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 23:53
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
