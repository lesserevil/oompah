---
id: OOMPAH-585
type: epic
status: In Validation
priority: 1
title: Restore terminal-audit execution and truthful health reporting
parent: OOMPAH-584
children:
- OOMPAH-589
- OOMPAH-590
- OOMPAH-591
- OOMPAH-592
- OOMPAH-604
- OOMPAH-616
- OOMPAH-618
- OOMPAH-622
- OOMPAH-625
- OOMPAH-626
- OOMPAH-627
- OOMPAH-628
- OOMPAH-629
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:13:32.577860Z'
updated_at: '2026-08-03T21:34:48.423860Z'
work_branch: epic-OOMPAH-585
target_branch: epic-OOMPAH-584
review_url: https://github.com/lesserevil/oompah/pull/596
review_number: '596'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/596
oompah.review_number: '596'
oompah.work_branch: epic-OOMPAH-585
oompah.target_branch: epic-OOMPAH-584
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-b4197d025ad2: '2026-07-31T00:12:17.042224+00:00'
    attempt-e6d2d009f03d: '2026-07-31T00:16:01.210909+00:00'
    attempt-12fe57be5937: '2026-08-03T20:51:35.221538+00:00'
  oompah.terminal_override_records: []
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-585
    target_state: Merged
    evidence_fingerprint: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    audit_ids:
    - audit-a98f5ed965f0
    kind: result
    applied: false
    retired_at: '2026-08-03T20:51:35.221544+00:00'
    lifecycle_reconciled: true
    reconciled_to: Done
    retired_reason: shared_epic_parent_not_landed
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-585
    audit_id: audit-a98f5ed965f0
    attempt_id: attempt-12fe57be5937
    target_state: Merged
    evidence_fingerprint: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    status: Merged
    audit_ids:
    - audit-a98f5ed965f0
    applied: true
    created_at: '2026-08-03T20:51:35.221553+00:00'
    applied_at: '2026-08-03T20:51:41.193326+00:00'
    retired_by_reconciliation: true
    retired_reason: shared_epic_parent_not_landed
    reconciled_at: '2026-08-03T21:03:27.100292+00:00'
  oompah.lifecycle_reconciliations:
  - project_id: proj-14849f1b
    task_id: OOMPAH-585
    from: Merged
    to: Done
    reason: shared_epic_parent_not_landed
    conflict: 'Cannot transition shared-epic child OOMPAH-585 to Merged: parent epic
      OOMPAH-584 could not be verified. The parent review must land on its configured
      target branch first.'
    done_audit_ids:
    - audit-0b310adb4fa7
    created_at: '2026-08-03T20:02:49.545800+00:00'
  - project_id: proj-14849f1b
    task_id: OOMPAH-585
    from: Merged
    to: Done
    reason: shared_epic_parent_not_landed
    conflict: 'Cannot transition shared-epic child OOMPAH-585 to Merged: parent epic
      OOMPAH-584 could not be verified. The parent review must land on its configured
      target branch first.'
    done_audit_ids:
    - audit-0b310adb4fa7
    created_at: '2026-08-03T21:03:27.100292+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0b310adb4fa7
    project_id: proj-14849f1b
    task_id: OOMPAH-585
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    attempts:
    - version: 1
      attempt_id: attempt-49359e458701
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
      created_at: '2026-07-30T23:48:25.680746+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T23:48:25.680746+00:00'
      branch_key: epic-OOMPAH-585
      failure_classification: infrastructure_error
      ended_at: '2026-07-30T23:57:12.903573+00:00'
      failure_reason: normal
      next_retry_at: '2026-07-30T23:57:22.903546+00:00'
    - version: 1
      attempt_id: attempt-b4197d025ad2
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
      created_at: '2026-07-31T00:03:51.620034+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-07-31T00:03:51.620034+00:00'
      branch_key: epic-OOMPAH-585
      candidate_rotation_count: 1
      verdict: pass
      completed_at: '2026-07-31T00:12:17.042050+00:00'
      ended_at: '2026-07-31T00:12:17.042050+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T23:32:29.243227+00:00'
    updated_at: '2026-07-31T00:12:17.042050+00:00'
  - version: 1
    audit_id: audit-6806c4fdb604
    project_id: proj-14849f1b
    task_id: OOMPAH-585
    target_state: Merged
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    attempts:
    - version: 1
      attempt_id: attempt-e6d2d009f03d
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
      created_at: '2026-07-31T00:12:46.095751+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T00:12:46.095751+00:00'
      branch_key: epic-OOMPAH-585
      verdict: pass
      completed_at: '2026-07-31T00:16:01.210764+00:00'
      ended_at: '2026-07-31T00:16:01.210764+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T23:32:29.243227+00:00'
    updated_at: '2026-08-03T20:02:49.545800+00:00'
  - version: 1
    audit_id: audit-a98f5ed965f0
    project_id: proj-14849f1b
    task_id: OOMPAH-585
    target_state: Merged
    request_state: superseded
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    attempts:
    - version: 1
      attempt_id: attempt-12fe57be5937
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
      created_at: '2026-08-03T20:16:47.220623+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T20:16:47.220623+00:00'
      branch_key: epic-OOMPAH-585
      verdict: pass
      completed_at: '2026-08-03T20:51:35.221415+00:00'
      ended_at: '2026-08-03T20:51:35.221415+00:00'
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: In Review
    created_at: '2026-08-03T20:12:16.830557+00:00'
    updated_at: '2026-08-03T21:03:27.100292+00:00'
  - version: 1
    audit_id: audit-def73c9cef1d
    project_id: proj-14849f1b
    task_id: OOMPAH-585
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    attempts:
    - version: 1
      attempt_id: attempt-479bdb1b2159
      target_state: Merged
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
      created_at: '2026-08-03T21:16:15.509923+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T21:16:15.509923+00:00'
      branch_key: epic-OOMPAH-585
      failure_classification: policy_incompatibility
      ended_at: '2026-08-03T21:34:45.883539+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy permits only read-only repository inspection and
        configured test commands; command denied'
      next_retry_at: '2026-08-03T21:34:55.883513+00:00'
    requested_by:
      version: 1
      identity: epic-rollup-reconciliation
      source: oompah
    previous_state: Done
    created_at: '2026-08-03T21:05:27.366901+00:00'
    updated_at: '2026-08-03T21:34:45.883539+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-49359e458701
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    created_at: '2026-07-30T23:48:25.680746+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T23:48:25.680746+00:00'
    branch_key: epic-OOMPAH-585
    failure_classification: infrastructure_error
    ended_at: '2026-07-30T23:57:12.903573+00:00'
    failure_reason: normal
    next_retry_at: '2026-07-30T23:57:22.903546+00:00'
  - version: 1
    attempt_id: attempt-b4197d025ad2
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    created_at: '2026-07-31T00:03:51.620034+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-07-31T00:03:51.620034+00:00'
    branch_key: epic-OOMPAH-585
    candidate_rotation_count: 1
  - version: 1
    attempt_id: attempt-e6d2d009f03d
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    created_at: '2026-07-31T00:12:46.095751+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T00:12:46.095751+00:00'
    branch_key: epic-OOMPAH-585
  - version: 1
    attempt_id: attempt-12fe57be5937
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    created_at: '2026-08-03T20:16:47.220623+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T20:16:47.220623+00:00'
    branch_key: epic-OOMPAH-585
  - version: 1
    attempt_id: attempt-479bdb1b2159
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    created_at: '2026-08-03T21:16:15.509923+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T21:16:15.509923+00:00'
    branch_key: epic-OOMPAH-585
    failure_classification: policy_incompatibility
    ended_at: '2026-08-03T21:34:45.883539+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy permits only read-only repository inspection and configured
      test commands; command denied'
    next_retry_at: '2026-08-03T21:34:55.883513+00:00'
oompah.task_costs:
  total_input_tokens: 183
  total_output_tokens: 6191
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 183
      output_tokens: 6191
      cost_usd: 0.0
  runs:
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 89
    cost_usd: 0.0
    recorded_at: '2026-07-30T23:57:12.421230+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 3
    output_tokens: 87
    cost_usd: 0.0
    recorded_at: '2026-07-31T00:12:42.540710+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 62
    output_tokens: 2275
    cost_usd: 0.0
    recorded_at: '2026-07-31T00:16:20.226705+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 73
    output_tokens: 2300
    cost_usd: 0.0
    recorded_at: '2026-08-03T20:55:46.521791+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 39
    output_tokens: 1440
    cost_usd: 0.0
    recorded_at: '2026-08-03T21:34:44.077397+00:00'
---
## Summary

Goal

Make terminal auditing reliable and honestly observable from candidate selection through final tracker transition. Repair the malformed auditor-provider launch path, add bounded recovery, drain the current backlog, and ensure alerts represent execution failures rather than only metadata-enforcement failures.

Relevant context

Completion-auditor sessions for OOMPAH-580 and OOMPAH-582 failed with unknown URL type /chat/completions. The service reported 54 pending audits while the alert list was empty. Existing OOMPAH-460 covers terminal-audit product/UI work; this epic is limited to the uncovered runtime recovery and health-truth gap.

Acceptance criteria

Eligible auditors launch against validated absolute endpoints; invalid candidates fail closed with actionable safe diagnostics; pending requests retry without duplication; stale In Validation records reconcile; backlog age and launch failures generate durable alerts; recovered health clears alerts; focused and complete Makefile gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 23:31
---
Branch quality gate passed for `4510fb912aebc99dce90df1dc55e8ee952408401` using `make test` in 255.7s. Review creation may proceed.
---
author: oompah
created: 2026-07-30 23:32
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 23:48
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 23:48
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 23:57
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 81, Tool calls: 56
- Tokens: 6 in / 89 out [95 total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 46s
- Log: OOMPAH-585__20260730T234834Z.jsonl
---
author: oompah
created: 2026-07-30 23:57
---
Auditor attempt ended: auditor exited (normal) without a result. A different independent auditor will be tried on the next scheduler tick.
---
author: oompah
created: 2026-07-31 00:03
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-07-31 00:03
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 00:12
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- merge_commit: c45e47bb3bdf8f3424357dd499010d52322bd7cc
- gate_commit: 4510fb912aebc99dce90df1dc55e8ee952408401
- gate_result: make test passed in 255.7s
- pr: 596
- focused_tests_terminal_audit_health: 50 passed
- focused_tests_terminal_audit_suite: 332 passed
- focused_tests_candidate_selector: 49 passed
- focused_tests_dispatch: 13 passed
- focused_tests_enforcement: 18 passed
- focused_tests_close_race_cleanup: 24 passed
- focused_tests_integration_orchestrator: 365 passed
- focused_tests_provider_health: 167 passed
- new_module: oompah/terminal_audit_health.py (460 lines)
- changed_files: 31 files, 3388 insertions, 94 deletions
---
author: oompah
created: 2026-07-31 00:12
---
Run #2 [attempt=2, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 93, Tool calls: 60
- Tokens: 3 in / 87 out [90 total]
- Cost: $0.0000
- Exit: normal, Duration: 8m 50s
- Log: OOMPAH-585__20260731T000356Z.jsonl
---
author: oompah
created: 2026-07-31 00:12
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 00:12
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 00:16
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- merge_commit: c45e47bb3bdf8f3424357dd499010d52322bd7cc
- gate_commit: 4510fb912aebc99dce90df1dc55e8ee952408401
- pr: 596
- gate_result: make test passed in 255.7s (per branch quality gate comment)
- merged_into: origin/epic-OOMPAH-584 (parent epic branch)
- changed_files: 31 files, 3388 insertions, 94 deletions
- new_module: oompah/terminal_audit_health.py (460 lines)
- focused_terminal_audit_health: 32 passed
- focused_dashboard_terminal_audit_health: 16 passed
- focused_terminal_audit_health_api: 2 passed
- focused_auditor_candidate_selector: 49 passed
- focused_auditor_dispatch: 13 passed
- focused_terminal_audit_enforcement_and_coordinator: 124 passed
- focused_dispatch_close_race: 22 passed
- focused_auditor_termination_cleanup: 2 passed
- focused_provider_health: 64 passed
- children_done: OOMPAH-589, 591, 592, 604, 616, 618, 622, 625, 626, 627, 628, 629 (Done)
- child_note_ooompah_590: Child OOMPAH-590 metadata shows Needs Human, but its implementation commit cc2614933 is present on origin/epic-OOMPAH-584 and the covered retry behavior is exercised by passing tests.
- acceptance_criteria_status: All addressed: absolute-endpoint validation, safe diagnostics, retry without duplication, stale-validation reconciliation, durable failure and backlog alerts, health module with degraded flag, focused tests pass, branch gate passed.
---
author: oompah
created: 2026-07-31 00:16
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 42
- Tokens: 62 in / 2.3K out [2.3K total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 33s
- Log: OOMPAH-585__20260731T001250Z.jsonl
---
author: oompah
created: 2026-08-03 20:02
---
Lifecycle reconciliation restored OOMPAH-585 to audited Done: Cannot transition shared-epic child OOMPAH-585 to Merged: parent epic OOMPAH-584 could not be verified. The parent review must land on its configured target branch first.
---
author: oompah
created: 2026-08-03 20:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 20:16
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 20:51
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- task_id: OOMPAH-585
- previous_state: In Review
- tracker_state_now: In Validation
- requested_target: Merged
- main_head_now: 576a85bfc
- pr_number: 596
- pr_merge_commit_on_main: b98d6400c9a6b2addd53cb931770065621657ebc
- pr_second_parent_landed: 65abaafc680a1ae5e5751fab5257c92ac5723df6
- prior_gate_commit_alt_head: 4510fb912aebc99dce90df1dc55e8ee952408401
- parent_epic_task: OOMPAH-584
- parent_epic_merge_commit_on_main: bb0fd760c3b2938d15ec2026ef5bfc2fd34b0682
- parent_epic_pr_number: 603
- prior_lifecycle_block: 2026-08-03 parent OOMPAH-584 unverified; now resolved on main
- children_all_terminal: 13/13 Done or Merged
- new_module_on_main: oompah/terminal_audit_health.py at 64b9b00c5 (OOMPAH-592)
- prior_gate_result: make test 255.7s pass on 4510fb912ae
- prior_focused_tests_summary: terminal_audit_health 32, dashboard 16, api 2, candidate_selector 49, dispatch 13, enforcement 124, close_race 22, termination 2, provider_health 64 all pass
- acceptance_criteria_status: All satisfied: endpoint validation, safe diagnostics, retry without duplication, stale-validation reconciliation, launch/backlog alerts, recovered-health clearing, full Makefile gate
---
author: oompah
created: 2026-08-03 20:55
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 47
- Tokens: 73 in / 2.3K out [2.4K total]
- Cost: $0.0000
- Exit: terminated, Duration: 38m 56s
- Log: OOMPAH-585__20260803T201658Z.jsonl
---
author: oompah
created: 2026-08-03 21:03
---
Lifecycle reconciliation restored OOMPAH-585 to audited Done: Cannot transition shared-epic child OOMPAH-585 to Merged: parent epic OOMPAH-584 could not be verified. The parent review must land on its configured target branch first.
---
author: oompah
created: 2026-08-03 21:16
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 21:16
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 21:34
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 25
- Tokens: 39 in / 1.4K out [1.5K total]
- Cost: $0.0000
- Exit: terminated, Duration: 18m 18s
- Log: OOMPAH-585__20260803T211635Z.jsonl
---
<!-- COMMENTS:END -->
