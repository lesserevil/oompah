---
id: OOMPAH-610
type: bug
status: In Validation
priority: 1
title: Release stale claimed_issues entries when completion auditors exit
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T18:53:05.632137Z'
updated_at: '2026-08-06T20:43:42.541366Z'
work_branch: OOMPAH-610
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/594
review_number: '594'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bc294a0c7385189335b6f506d2ae07b096e00f7fb10f230cc9acd1e7494ff87f
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T18:58:45.299450+00:00'
  matched_identifiers: []
  evidence: 'Focus handoff: duplicate_detector


    Duplicate preflight verdict: no_duplicate


    Matches: none


    Evidence: Reviewed active OOMPAH-591, OOMPAH-592, OOMPAH-593, and OOMPAH-599.
    None covers completion-auditor exit cleanup of `state.claimed_issues` and audit-branch
    claims. OOMPAH-590 is the closest predecessor but is terminal (`Done`) and excluded.'
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 3514c39c-c179-4c65-a97c-34fc1997be79
oompah.task_costs:
  total_input_tokens: 2401095
  total_output_tokens: 33565
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 2400917
      output_tokens: 10209
      cost_usd: 0.0
    opus:
      input_tokens: 64
      output_tokens: 1645
      cost_usd: 0.0
    unknown:
      input_tokens: 114
      output_tokens: 21711
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 2400319
    output_tokens: 10074
    cost_usd: 0.0
    recorded_at: '2026-07-30T18:58:45.298050+00:00'
  - profile: default
    model: haiku
    input_tokens: 598
    output_tokens: 135
    cost_usd: 0.0
    recorded_at: '2026-07-30T19:01:42.918187+00:00'
  - profile: deep
    model: opus
    input_tokens: 64
    output_tokens: 1645
    cost_usd: 0.0
    recorded_at: '2026-07-30T19:08:23.056668+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 83
    output_tokens: 20935
    cost_usd: 0.0
    recorded_at: '2026-07-30T19:33:31.731439+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 31
    output_tokens: 776
    cost_usd: 0.0
    recorded_at: '2026-07-30T19:37:35.113256+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-610__20260730T185400Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-610
    source_sha: b4fa5db81322ae24b90a5c80689d94d1a49a1f30
    completed_at: '2026-07-30T18:58:45.304450+00:00'
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-610
  head_sha: 83949a45b38f10a844a40c679ca105dc3e456f01
  submitted_at: '2026-07-30T19:08:07.342076+00:00'
  updated_at: '2026-07-30T19:08:07.342076+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/594
oompah.review_number: '594'
oompah.work_branch: OOMPAH-610
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-9ad0fa99a03f: '2026-07-30T19:29:33.337559+00:00'
    attempt-7fac07b83954: '2026-07-30T19:37:05.502638+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-490436c776e7
    project_id: proj-14849f1b
    task_id: OOMPAH-610
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a45e32e03bb6f6616011264ecddde94b139adfb31d38a5a5649a12743cbd557
    attempts:
    - version: 1
      attempt_id: attempt-9ad0fa99a03f
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8a45e32e03bb6f6616011264ecddde94b139adfb31d38a5a5649a12743cbd557
      created_at: '2026-07-30T19:15:41.439054+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T19:15:41.439054+00:00'
      branch_key: OOMPAH-610
      verdict: pass
      completed_at: '2026-07-30T19:29:33.337337+00:00'
      ended_at: '2026-07-30T19:29:33.337337+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T19:15:33.898604+00:00'
    updated_at: '2026-07-30T19:29:33.337337+00:00'
  - version: 1
    audit_id: audit-e8bbf3386cc7
    project_id: proj-14849f1b
    task_id: OOMPAH-610
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a45e32e03bb6f6616011264ecddde94b139adfb31d38a5a5649a12743cbd557
    attempts:
    - version: 1
      attempt_id: attempt-7fac07b83954
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8a45e32e03bb6f6616011264ecddde94b139adfb31d38a5a5649a12743cbd557
      created_at: '2026-07-30T19:34:24.347503+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-30T19:34:24.347503+00:00'
      branch_key: OOMPAH-610
      verdict: pass
      completed_at: '2026-07-30T19:37:05.502397+00:00'
      ended_at: '2026-07-30T19:37:05.502397+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-30T19:15:33.898604+00:00'
    updated_at: '2026-07-30T19:37:05.502397+00:00'
  - version: 1
    audit_id: audit-0792a8f48e93
    project_id: proj-14849f1b
    task_id: OOMPAH-610
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f3cdbc2a7ba568ae0563863c51332bda5ce3e0a60137a4eabe8b0601bc4124fc
    attempts:
    - version: 1
      attempt_id: attempt-3cc33ac124a0
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f3cdbc2a7ba568ae0563863c51332bda5ce3e0a60137a4eabe8b0601bc4124fc
      created_at: '2026-08-06T20:43:22.520662+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-06T20:43:22.520662+00:00'
      branch_key: OOMPAH-610
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-06T20:42:19.193953+00:00'
    updated_at: '2026-08-06T20:43:22.520662+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-9ad0fa99a03f
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a45e32e03bb6f6616011264ecddde94b139adfb31d38a5a5649a12743cbd557
    created_at: '2026-07-30T19:15:41.439054+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T19:15:41.439054+00:00'
    branch_key: OOMPAH-610
  - version: 1
    attempt_id: attempt-7fac07b83954
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8a45e32e03bb6f6616011264ecddde94b139adfb31d38a5a5649a12743cbd557
    created_at: '2026-07-30T19:34:24.347503+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-30T19:34:24.347503+00:00'
    branch_key: OOMPAH-610
  - version: 1
    attempt_id: attempt-3cc33ac124a0
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f3cdbc2a7ba568ae0563863c51332bda5ce3e0a60137a4eabe8b0601bc4124fc
    created_at: '2026-08-06T20:43:22.520662+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-06T20:43:22.520662+00:00'
    branch_key: OOMPAH-610
---
## Summary

Triggered by: OOMPAH-590

Implementation scope: Fix the completion-auditor worker-exit path in oompah/orchestrator.py so every auditor exit removes the issue from both state.claimed and state.claimed_issues, releases its audit branch claim, and leaves the pending terminal-audit request eligible for candidate rotation or explicit no-auditor routing after backoff. Preserve ordinary-worker and duplicate-preflight cleanup behavior. Add defensive observability or invariant coverage if needed so a stale in-memory claim cannot silently suppress an In Validation request forever.\n\nRequired tests: Add a regression reproducing an auditor that exits stalled or errored without a structured result, then prove _audit_branch_busy is false after cleanup and the next audit-lane tick either dispatches the next independent candidate or routes exhaustion to Needs Human. Cover idempotent cleanup and retain existing auditor dispatch tests. Run focused scheduler/auditor tests and make test.\n\nAcceptance criteria: No ended auditor remains in state.claimed_issues; OOMPAH-593 and equivalent In Validation tasks cannot be silently skipped after retry_after; the scheduler reaches a new auditor or an actionable terminal outcome; all relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 18:53
---
Claimed by the interactive operator session for immediate self-hosting recovery. Root cause reproduced on OOMPAH-593: auditor exit clears state.claimed and the branch claim but leaves state.claimed_issues, causing _audit_branch_busy to suppress every retry after next_retry_at.
---
author: oompah
created: 2026-07-30 18:53
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 18:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 18:55
---
Implemented locally: auditor exit now removes state.claimed_issues in addition to state.claimed and the audit branch claim. The audit branch gate also prunes orphaned claimed_issues entries whose ID is absent from state.claimed, with a warning, while preserving active claim serialization. Added focused regressions for stalled auditor cleanup and defensive stale-claim pruning. Focused auditor/terminal suites: 298 passed; full gate next.
---
author: oompah
created: 2026-07-30 18:58
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 27
- Tokens: 2.4M in / 10.1K out [2.4M total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 47s
- Log: OOMPAH-610__20260730T185400Z.jsonl
---
author: oompah
created: 2026-07-30 18:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 18:59
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-30 19:01
---
Refactoring Specialist: understanding phase. The previous Duplicate Investigator identified the issue: auditor exits clear state.claimed and the branch claim but leave state.claimed_issues, causing stale claims to suppress retries. The fix needs to remove claimed_issues in addition to state.claimed during auditor exit. The working tree is currently clean; exploring codebase structure to locate the auditor worker-exit path and existing tests to establish baseline before implementing refactored solution.
---
author: oompah
created: 2026-07-30 19:01
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 34
- Tokens: 598 in / 135 out [733 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 38s
- Log: OOMPAH-610__20260730T185908Z.jsonl
---
author: oompah
created: 2026-07-30 19:03
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-30 19:03
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-07-30 19:06
---
Refactoring Specialist: understanding phase. The previous session's local changes did not get committed (worktree is clean, no diff vs main). Recreating the fix. Root cause confirmed at oompah/orchestrator.py:23069-23081 — the auditor exit path clears state.claimed and _audit_branch_claims but NOT state.claimed_issues. That leaves the entry in claimed_issues, and _audit_branch_busy at line 4279 treats any surviving claimed_issues entry with the same branch key as a live claim, silently suppressing every retry after retry_after. Plan: (1) add self.state.claimed_issues.pop(issue_id, None) to the auditor exit branch alongside the existing claimed.discard and audit_branch_claims.pop; (2) add defensive pruning in _audit_branch_busy so any claimed_issues entry whose ID is missing from state.claimed is discarded and warned about (idempotent belt-and-braces); (3) add regression tests exercising both auditor exit cleanup and the defensive pruning path.
---
author: oompah
created: 2026-07-30 19:08
---
Verification complete on pushed head 83949a45b: focused auditor/terminal suite 298 passed; isolated prior full-gate timing failure passed under xdist; final make test passed 13,726 with 7 skipped; terminal mutation scan and secret scan passed.
---
author: oompah
created: 2026-07-30 19:08
---
Release stale auditor claims on worker exit and self-heal orphaned claimed_issues at audit branch admission; add stalled-exit and active-claim regression coverage.
---
author: oompah
created: 2026-07-30 19:08
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 39
- Tokens: 64 in / 1.6K out [1.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 27s
- Log: OOMPAH-610__20260730T190400Z.jsonl
---
author: oompah
created: 2026-07-30 19:15
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-30 19:15
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 19:15
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 19:19
---
Operator audit evidence update: PR #594 merged as e1e4e0c9f after Python 3.11, 3.12, and 3.13 CI all passed; local make test passed 13,726 with 7 skipped. Please finish the read-only review and submit the structured audit result now. Do not attempt shell mutations.
---
author: oompah
created: 2026-07-30 19:29
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- pushed_head: 83949a45b38f10a844a40c679ca105dc3e456f01
- origin_ref: refs/remotes/origin/OOMPAH-610
- commits_ahead_of_main: 1
- files_changed: oompah/orchestrator.py (+12/-1), tests/test_auditor_exit_cleanup.py (+89/-0)
- orchestrator_change_lines: _audit_branch_busy prune at 4276-4288; auditor exit claimed_issues.pop at 23082
- commit_trailer_check: canonical oompah trailer present; no Anthropic/Claude/GPT co-author
- focused_tests_reran_local_main: test_terminal_audit 28, test_auditor_dispatch 7, test_auditor_focus/contract/result_api/candidate_selector 139, test_orchestrator_handlers+dispatch_lane_contract+stalled_task_watchdog 385, terminal_audit_enforcement/metadata/scanner/override/status_interfaces/transition_coordinator 186 — 745 passed 0 failed
- prior_make_test_report: 13,726 passed / 7 skipped at 83949a45b per operator comment 2026-07-30 19:08
- auditor_exit_path: oompah/orchestrator.py::Orchestrator._on_worker_exit is_auditor branch (line 23069-23083)
- defensive_pruning: orphan claimed_issues entries missing from state.claimed are popped with warning log in _audit_branch_busy
---
author: oompah
created: 2026-07-30 19:32
---
Operator handoff: your first PASS was durably accepted. Audit audit-490436c776e7 is completed, attempt attempt-9ad0fa99a03f is recorded, and the next Merged audit is pending. The tool's rejection text came from a 60-second ACP handler timeout after the successful write. Do not retry this completed Done audit; end this auditor session now so the graceful restart can deploy the fix.
---
author: oompah
created: 2026-07-30 19:33
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 103, Tool calls: 77
- Tokens: 83 in / 20.9K out [21.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 17m 49s
- Log: OOMPAH-610__20260730T191549Z.jsonl
---
author: oompah
created: 2026-07-30 19:34
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-30 19:34
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-30 19:37
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- pushed_head: 83949a45b38f10a844a40c679ca105dc3e456f01
- merge_commit: e1e4e0c9fee2a17b5a9b02002fcaa2d3cc7793ec
- merge_pr: #594
- merged_into: origin/main
- ancestor_check: 83949a45b is ancestor of origin/main; only e1e4e0c9f sits above it
- files_changed: oompah/orchestrator.py (+12/-1), tests/test_auditor_exit_cleanup.py (+89/-0)
- orchestrator_change_lines: _audit_branch_busy orphan prune at 4276-4288; auditor exit claimed_issues.pop at 23082
- commit_trailer_check: canonical oompah trailer present; no Anthropic/Claude/GPT co-author
- prior_done_audit: audit-490436c776e7 completed PASS at 2026-07-30 19:29 per operator handoff
- focused_tests_reran_local_main: test_terminal_audit 28, test_auditor_dispatch 7, test_auditor_focus/contract/result_api/candidate_selector 139, test_orchestrator_handlers+dispatch_lane_contract+stalled_task_watchdog 385, terminal_audit_enforcement/metadata/scanner/override/status_interfaces/transition_coordinator 186 — 745 passed 0 failed
- prior_make_test_report: 13,726 passed / 7 skipped at 83949a45b per operator comment 2026-07-30 19:08
- ci_report: PR #594 CI green on Python 3.11, 3.12, 3.13 per operator comment 2026-07-30 19:19
---
author: oompah
created: 2026-07-30 19:37
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 15
- Tokens: 31 in / 776 out [807 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 8s
- Log: OOMPAH-610__20260730T193429Z.jsonl
---
author: oompah
created: 2026-08-06 20:43
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-06 20:43
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
