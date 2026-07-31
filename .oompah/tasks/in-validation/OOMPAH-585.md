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
updated_at: '2026-07-31T00:12:50.168256Z'
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
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0cfb98eafc768e5e2b01af3fc05a46d57c2174f15a248e0583518caca77a559e
    attempts:
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
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T23:32:29.243227+00:00'
    updated_at: '2026-07-31T00:12:46.095751+00:00'
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
oompah.task_costs:
  total_input_tokens: 9
  total_output_tokens: 176
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 9
      output_tokens: 176
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
<!-- COMMENTS:END -->
