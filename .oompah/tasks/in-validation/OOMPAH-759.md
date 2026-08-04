---
id: OOMPAH-759
type: bug
status: In Validation
priority: 1
title: Preserve focus-handoff authority across Open-to-In-Progress retry dispatch
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:23:16.197569Z'
updated_at: '2026-08-04T12:46:10.066755Z'
work_branch: OOMPAH-759
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/710
review_number: '710'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: bb6e8c860a59e485f7fe05ccb24c81ede6c25855a124e618d66b211dbe3fab1d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T11:26:05.807958+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed the supplied peer corpus; no active nonterminal\
    \ task covers this retry-dispatch authority regression. Closest candidates, OOMPAH-10\
    \ and OOMPAH-270, are archived and address unrelated tracker-sync and git-lock\
    \ issues.\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: Reviewed the supplied peer corpus; no active\
    \ nonterminal task covers this retry-dispatch authority regression. Closest candidates,\
    \ OOMPAH-10 and OOMPAH-270, are archived and address unrelated tracker-sync and\
    \ git-lock issues."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.task_costs:
  total_input_tokens: 46975
  total_output_tokens: 872
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46969
      output_tokens: 294
      cost_usd: 0.0
    unknown:
      input_tokens: 6
      output_tokens: 578
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46969
    output_tokens: 294
    cost_usd: 0.0
    recorded_at: '2026-08-04T11:26:05.806108+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 6
    output_tokens: 578
    cost_usd: 0.0
    recorded_at: '2026-08-04T12:46:07.609670+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-759__20260804T112522Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-759
    source_sha: 5368e23617a98569caf7370b0f2eb63d41c8ba6b
    completed_at: '2026-08-04T11:26:05.823955+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-759
  head_sha: 1c5572c87ba76dd501dbe3911838fd9ec40a83a8
  submitted_at: '2026-08-04T12:18:18.497844+00:00'
  updated_at: '2026-08-04T12:18:18.497844+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/710
oompah.review_number: '710'
oompah.work_branch: OOMPAH-759
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-6658a7bdd0f5: '2026-08-04T12:45:28.134906+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-759
    target_state: Done
    evidence_fingerprint: 9a9fd7a84fc5d0ccc3609250873ae576d296fcddc5ec60d7de731ba8176ea64e
    audit_ids:
    - audit-c00f0935bb4c
    kind: result
    applied: true
    retired_at: '2026-08-04T12:45:28.134918+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-759
    audit_id: audit-c00f0935bb4c
    attempt_id: attempt-6658a7bdd0f5
    target_state: Done
    evidence_fingerprint: 9a9fd7a84fc5d0ccc3609250873ae576d296fcddc5ec60d7de731ba8176ea64e
    status: In Validation
    audit_ids:
    - audit-c00f0935bb4c
    applied: true
    created_at: '2026-08-04T12:45:28.134933+00:00'
    applied_at: '2026-08-04T12:45:33.143770+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-c00f0935bb4c
    project_id: proj-14849f1b
    task_id: OOMPAH-759
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9a9fd7a84fc5d0ccc3609250873ae576d296fcddc5ec60d7de731ba8176ea64e
    attempts:
    - version: 1
      attempt_id: attempt-6658a7bdd0f5
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 9a9fd7a84fc5d0ccc3609250873ae576d296fcddc5ec60d7de731ba8176ea64e
      created_at: '2026-08-04T12:39:13.837345+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T12:39:13.837345+00:00'
      branch_key: OOMPAH-759
      verdict: pass
      completed_at: '2026-08-04T12:45:28.134740+00:00'
      ended_at: '2026-08-04T12:45:28.134740+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-04T12:38:40.560380+00:00'
    updated_at: '2026-08-04T12:45:28.134740+00:00'
  - version: 1
    audit_id: audit-dd5cb27447dd
    project_id: proj-14849f1b
    task_id: OOMPAH-759
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9a9fd7a84fc5d0ccc3609250873ae576d296fcddc5ec60d7de731ba8176ea64e
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-04T12:38:40.560380+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-6658a7bdd0f5
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 9a9fd7a84fc5d0ccc3609250873ae576d296fcddc5ec60d7de731ba8176ea64e
    created_at: '2026-08-04T12:39:13.837345+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T12:39:13.837345+00:00'
    branch_key: OOMPAH-759
---
## Summary

Triggered by: OOMPAH-757

Triggered by: OOMPAH-757

Live regression on revision 5368e236 in the retry-generation fence introduced by OOMPAH-684. A completed Technical Writer focus correctly handed OOMPAH-757 back to Open and reconciliation scheduled a fresh deep-profile retry. At 11:19:57 UTC the retry dispatch claimed the task and performed its own Open -> In Progress write; at 11:20:19 it logged 'Aborting retry before worker start' and removed the process claim, but left OOMPAH-757 In Progress with no running agent. The final retry CAS computes post_authority_changed by comparing the post-write In Progress state to the captured pre-write Open state, so the dispatch invalidates itself even though assignment, branch, head, and task authority remain unchanged. This strands normal focus handoffs and can recur after any retry sourced from an active state other than In Progress.

Implementation scope: distinguish the dispatcher's authorized Open -> In Progress transition from an external status change in the final retry compare-and-swap; validate the post-write state against the intended active state while comparing branch/head/assignment and exact retry generation against pre-write authority; if any final CAS abort happens after the dispatcher wrote In Progress, atomically restore the prior retryable status or immediately install a replacement dispatch owner so no orphaned In Progress task remains; preserve the OOMPAH-684 stale-submit/terminal fences and fail closed on real operator edits, accepted submissions, head drift, assignment changes, cancellation, and terminal ownership. Add explicit structured diagnostics for the failed authority dimension.

Relevant code: Orchestrator._dispatch final retry CAS and post_authority_changed calculation, _on_retry_timer, _retry_entry_matches_issue, focus-handoff completion/reconciliation, retry cancellation, orphan recovery, and persisted retry restart handling.

Required tests: exact OOMPAH-757 Technical Writer handoff Open -> scheduled retry -> self-authored In Progress -> replacement Feature Developer starts; ordinary retry already In Progress; operator status change during setup; accepted submission during setup; branch/head/assignment drift; cancellation and terminal fence; abort after tracker write leaves Open/retry-owned rather than orphaned In Progress; restart between handoff, retry claim, and provider start. Acceptance criteria: a completed focus handoff naturally starts the next applicable focus exactly once; an authorized retry does not reject its own status write; every pre-start abort leaves either a live owner or a dispatchable nonterminal state; stale external authority still wins; focused dispatch/retry/handoff/race/restart tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 11:25
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 11:25
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 11:26
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.0K in / 294 out [47.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 7s
- Log: OOMPAH-759__20260804T112522Z.jsonl
---
author: oompah
created: 2026-08-04 11:28
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 11:28
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-04 11:55
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 104
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 26m 56s
- Log: OOMPAH-759__20260804T112820Z.jsonl
---
author: oompah
created: 2026-08-04 11:55
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 11:55
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-04 11:56
---
Understanding: the retry dispatcher must treat its own Open -> In Progress write as authorized, while preserving generation and external-authority fences. I am reviewing the preserved checkpoint, then will ensure every post-write pre-start abort restores a dispatchable prior state (or retains a live owner), add dimension-specific diagnostics, cover handoff/race/restart paths, and run focused Makefile-based checks before push and submission.
---
author: oompah
created: 2026-08-04 11:59
---
Discovery: the preserved checkpoint correctly identifies the core fault: final retry validation compared the post-write In Progress status to the captured Open generation. The fix needs a two-snapshot CAS—pre-write generation/status authority, then post-write intended-active status plus unchanged task/project/assignment/branch/head. Audit also found pre-start exits after the status write (shared claim/terminal/read failures) must explicitly transfer or recover ownership; merely rearming the original Open generation can later self-cancel against In Progress and strand the task.
---
author: oompah
created: 2026-08-04 12:15
---
Implementation: retry entries now durably record dispatcher-authored status and assignment intents while retaining the exact pre-write authority generation. Final CAS accepts only the intended active state/new run ID plus unchanged task/project/branch/head authority; mismatches report structured dimensions. Pre-start abort recovery restores the captured dispatchable status, or keeps a persisted retry owner when rollback is temporarily unavailable. Timer, reconciliation, and restart paths now recover the same claim without overriding submission, cancellation, terminal, or operator authority.
---
author: oompah
created: 2026-08-04 12:16
---
Verification: focused retry/dispatch/owner/submission/focus suites passed (168 tests), followed by a post-rebase retry + worker-submission + close-race run (72 tests). The Makefile terminal-audit scan also passed (8/8 mutations allowlisted), and git diff --check is clean. Coverage includes Open and already-In-Progress retries, Technical Writer -> Feature Developer handoff exactly once, authorized run-ID assignment, operator/submission/cancellation/terminal fences, branch/head/assignment drift diagnostics, rollback failure ownership, and valid/stale restart recovery.
---
author: oompah
created: 2026-08-04 12:18
---
Completion: delivered and pushed commit 1c5572c87. Retry dispatch now preserves pre-write generation authority while durably owning its Open -> In Progress status/run-ID handoff across setup failures and restarts; real operator, submission, cancellation, terminal, branch, head, and assignment changes still fence launch. Aborted claims restore a dispatchable state or retain a live recovery timer. Focused race/restart/handoff suites and terminal/secret scans pass; branch is synchronized with origin.
---
author: oompah
created: 2026-08-04 12:18
---
Preserved retry focus-handoff authority across self-authored In Progress and assignment claims, added atomic rollback/live-owner recovery with restart persistence, retained external authority fences, and covered handoff/race/restart paths.
---
author: oompah
created: 2026-08-04 12:19
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 0, Tool calls: 95
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 23m 29s
- Log: OOMPAH-759__20260804T115554Z.jsonl
---
author: oompah
created: 2026-08-04 12:29
---
Branch quality gate passed for `1c5572c87ba76dd501dbe3911838fd9ec40a83a8` using `make test` in 450.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-04 12:38
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-04 12:38
---
YOLO: merged PR #710.
---
author: oompah
created: 2026-08-04 12:39
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 12:39
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 12:45
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_sha: 1c5572c87ba76dd501dbe3911838fd9ec40a83a8
- merge_commit: 5841eb680383563da6b5a5a6a96363b0b1463b4d
- pull_request: #710
- focused_tests_passed: 213
- focused_test_files: test_retry_authority_generation.py,test_dispatch_close_race.py,test_worker_submission.py,test_focus.py
- diff_stat: oompah/models.py +6, oompah/orchestrator.py +727/-73, tests/test_retry_authority_generation.py +601
- branch_quality_gate: make test passed for 1c5572c87 in 450.3s (per task history)
- commit_trailer: canonical oompah trailer, no model attribution
---
author: oompah
created: 2026-08-04 12:46
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 37, Tool calls: 26
- Tokens: 6 in / 578 out [584 total]
- Cost: $0.0000
- Exit: normal, Duration: 6m 43s
- Log: OOMPAH-759__20260804T123932Z.jsonl
---
<!-- COMMENTS:END -->
