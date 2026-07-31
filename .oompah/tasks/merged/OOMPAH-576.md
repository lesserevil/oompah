---
id: OOMPAH-576
type: task
status: Merged
priority: null
title: Reject integration submissions from the wrong checkout before mutating task
  worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T02:55:54.699694Z'
updated_at: '2026-07-31T02:44:13.284759Z'
work_branch: OOMPAH-576
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/599
review_number: '599'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3a0d0bdf76fa62b3007a3a55c9f010ba8c5e02c9d7ca4e709421b245ffd9f644
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-30T13:36:23.277930+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I have searched the entire tracker\
    \ for related tasks and found no active duplicate of OOMPAH-576.\n\n## Investigation\
    \ Summary\n\n**Searched locations:**\n- All open tasks (.oompah/tasks/open/):\
    \ OOMPAH-281, OOMPAH-282\n- All backlog tasks (.oompah/tasks/backlog/): OOMPAH-282\n\
    - All merged tasks (.oompah/tasks/merged/): OOMPAH-271, OOMPAH-272, OOMPAH-275,\
    \ OOMPAH-277, OOMPAH-278, OOMPAH-279, OOMPAH-280 (all are rebase operations for\
    \ epic-OOMPAH-253)\n- 300+ archived tasks: none matched\n- Design documents in\
    \ `plans/`: submit-queue.md (about GitHub Merge Queue and PR concurrency, different\
    \ scope), terminal-audit-enforcement.md (OOMPAH-483, about terminal state validation,\
    \ not submission validation)\n\n**Search queries used:**\n- `OOMPAH-483` (the\
    \ regression mentioned in the issue)\n- Keywords: `worktree`, `integration`, `submission`,\
    \ `queue`, `executor`, `submit`, `branch`\n- Patterns: `(submit.*worktree|integration.*worktree|task.*submission)`,\
    \ `(branch.*valid|branch.*check)`, `(reset.*worktree|mutation.*protect)`\n\n**Result:**\n\
    All matches found are in terminal states (Done, Merged, or Archived). The only\
    \ potentially related task is OOMPAH-483, which handles terminal-state audit enforcement\
    \ after tasks are marked Done \u2014 not submission validation before mutations.\n\
    \n**Conclusion:**\nOOMPAH-576 addresses a unique hardening requirement: rejecting\
    \ task submissions from the wrong checkout before mutating worktrees. No existing\
    \ open, in-progress, or active task covers this scope.\n\n---\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** Comprehensive search of .oompah/tasks/ across all states\
    \ (open, backlog, merged, archived), plans/submit-queue.md, and terminal-audit-enforcement.md\
    \ returned no active tasks covering task submission checkout validation, integration\
    \ worktree protection, or prevention of destructive resets from wrong-checkout\
    \ submissions. OOMPAH-576 is a unique, first-of-"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: efdafb9f-1316-4c86-8661-f667cb1c7e8c
oompah.task_costs:
  total_input_tokens: 5596648
  total_output_tokens: 36732
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 129304
      output_tokens: 6328
      cost_usd: 0.0
    sonnet:
      input_tokens: 5467272
      output_tokens: 24362
      cost_usd: 0.0
    opus:
      input_tokens: 37
      output_tokens: 859
      cost_usd: 0.0
    unknown:
      input_tokens: 35
      output_tokens: 5183
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 154
    output_tokens: 5287
    cost_usd: 0.0
    recorded_at: '2026-07-30T13:36:23.277495+00:00'
  - profile: default
    model: haiku
    input_tokens: 129150
    output_tokens: 1041
    cost_usd: 0.0
    recorded_at: '2026-07-30T13:37:23.091141+00:00'
  - profile: standard
    model: sonnet
    input_tokens: 5467272
    output_tokens: 24362
    cost_usd: 0.0
    recorded_at: '2026-07-30T13:46:49.494063+00:00'
  - profile: deep
    model: opus
    input_tokens: 37
    output_tokens: 859
    cost_usd: 0.0
    recorded_at: '2026-07-30T13:49:12.678149+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 35
    output_tokens: 5183
    cost_usd: 0.0
    recorded_at: '2026-07-31T02:40:51.519537+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-576__20260730T133433Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-576
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T13:36:23.281695+00:00'
  - run_id: OOMPAH-576__20260730T133636Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: general
    source_branch: OOMPAH-576
    source_sha: 12f63352ba017c6ffe88b0ca730bf3f7f973304e
    completed_at: '2026-07-30T13:37:23.095700+00:00'
  - run_id: OOMPAH-576__20260730T133747Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-terra
    focus: general
    source_branch: OOMPAH-576
    source_sha: 6f5a859b215c0a9a4744984e89b27e3fe990050d
    completed_at: '2026-07-30T13:46:49.498181+00:00'
oompah.integration:
  version: 1
  state: ready
  attempts: 0
  task_branch: OOMPAH-576
  head_sha: 6f5a859b215c0a9a4744984e89b27e3fe990050d
  submitted_at: '2026-07-30T13:48:56.421801+00:00'
  updated_at: '2026-07-30T13:48:56.421801+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/599
oompah.review_number: '599'
oompah.work_branch: OOMPAH-576
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-558c6911dda7: '2026-07-31T02:40:35.964619+00:00'
    attempt-f3c46f01b5ac: '2026-07-31T02:44:10.430554+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-38593917d6d9
    project_id: proj-14849f1b
    task_id: OOMPAH-576
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8230cff302d77015c8b65bf822db7a071e4723f4dfa98b52b2efce394b40a17b
    attempts:
    - version: 1
      attempt_id: attempt-558c6911dda7
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8230cff302d77015c8b65bf822db7a071e4723f4dfa98b52b2efce394b40a17b
      created_at: '2026-07-31T02:37:47.588093+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T02:37:47.588093+00:00'
      branch_key: OOMPAH-576
      verdict: pass
      completed_at: '2026-07-31T02:40:35.964530+00:00'
      ended_at: '2026-07-31T02:40:35.964530+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T02:37:30.421048+00:00'
    updated_at: '2026-07-31T02:40:35.964530+00:00'
  - version: 1
    audit_id: audit-e4ce4c1b8864
    project_id: proj-14849f1b
    task_id: OOMPAH-576
    target_state: Merged
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8230cff302d77015c8b65bf822db7a071e4723f4dfa98b52b2efce394b40a17b
    attempts:
    - version: 1
      attempt_id: attempt-f3c46f01b5ac
      target_state: Merged
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 8230cff302d77015c8b65bf822db7a071e4723f4dfa98b52b2efce394b40a17b
      created_at: '2026-07-31T02:41:03.194379+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-07-31T02:41:03.194379+00:00'
      branch_key: OOMPAH-576
      verdict: pass
      completed_at: '2026-07-31T02:44:10.430396+00:00'
      ended_at: '2026-07-31T02:44:10.430396+00:00'
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T02:37:30.421048+00:00'
    updated_at: '2026-07-31T02:44:10.430396+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-558c6911dda7
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8230cff302d77015c8b65bf822db7a071e4723f4dfa98b52b2efce394b40a17b
    created_at: '2026-07-31T02:37:47.588093+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T02:37:47.588093+00:00'
    branch_key: OOMPAH-576
  - version: 1
    attempt_id: attempt-f3c46f01b5ac
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8230cff302d77015c8b65bf822db7a071e4723f4dfa98b52b2efce394b40a17b
    created_at: '2026-07-31T02:41:03.194379+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-07-31T02:41:03.194379+00:00'
    branch_key: OOMPAH-576
---
## Summary

Implementation scope: harden task submission and integration worktree preparation so a submission made from the service/default-branch checkout cannot overwrite an existing task's recorded work branch or reset that task's live worktree to origin/main. Validate that the submitted local branch matches the task's expected work-branch namespace and pushed remote head before updating the queue; make integration worktree preparation fail closed when the queue branch disagrees with an already-registered worktree branch, without running reset. Relevant context/files: oompah/task_cli.py submit payload construction, server submit endpoint, oompah/integration_queue.py, oompah/integration_executor.py, and ProjectStore worktree preparation. Regression observed on OOMPAH-483: submitting from /home/shedwards/src/oompah queued task_branch=main, then the executor reset the registered epic-OOMPAH-459--task-OOMPAH-483 worktree from bc448cf08 to origin/main; the remote branch preserved the work and an operator restored it by fast-forward. Tests: cover wrong-checkout submit rejection, unchanged queue record, unchanged registered task worktree HEAD/branch, correct task-worktree resubmission, and no destructive reset on branch mismatch. Acceptance criteria: wrong-checkout submission returns an actionable error before tracker/queue/worktree mutation; correct submissions still integrate; a malformed/stale queue row cannot rewrite a registered worktree.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 13:34
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-30 13:34
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-30 13:36
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 61, Tool calls: 35
- Tokens: 154 in / 5.3K out [5.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 55s
- Log: OOMPAH-576__20260730T133433Z.jsonl
---
author: oompah
created: 2026-07-30 13:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-30 13:36
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 13:37
---
Agent completed successfully in 52s (130191 tokens)
---
author: oompah
created: 2026-07-30 13:37
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 3
- Tokens: 129.2K in / 1.0K out [130.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 52s
- Log: OOMPAH-576__20260730T133636Z.jsonl
---
author: oompah
created: 2026-07-30 13:37
---
Agent completed without landing — no commits found on origin for branch `OOMPAH-576`. Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-30 13:37
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-30 13:37
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 13:46
---
Agent completed successfully in 544s (5491634 tokens)
---
author: oompah
created: 2026-07-30 13:46
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 1, Tool calls: 45
- Tokens: 5.5M in / 24.4K out [5.5M total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 4s
- Log: OOMPAH-576__20260730T133747Z.jsonl
---
author: oompah
created: 2026-07-30 13:46
---
Agent completed without closing this issue (544s (5491634 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-30 13:47
---
Retrying (attempt #2, agent: deep)
---
author: oompah
created: 2026-07-30 13:47
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-30 13:48
---
Continuation run: verified the previously landed commit 6f5a859b2 covers the full scope. The change wires validate_submission_branch through both the ACP direct-submit path (oompah/acp_tools.py) and the HTTP submit endpoint (oompah/server.py); adds branch-identity checks with fail-closed behavior in oompah/projects.py::_reset_existing_worktree and oompah/integration_executor.py::execute_integration; and introduces expected_submission_branch/validate_submission_branch in oompah/integration.py. Focused tests exercise wrong-checkout ACP submit rejection, wrong-checkout HTTP submit rejection with unchanged queue, correct-checkout enqueue, worktree preparation refusal on branch mismatch (no reset/clean), and executor branch_mismatch without reset.
---
author: oompah
created: 2026-07-30 13:48
---
Verification: ran focused pytest suite for tests/test_projects.py, tests/test_integration_executor.py, tests/test_integration_record.py, tests/test_task_handoff.py, and tests/test_worker_submission.py — 125 passed, 0 failures. All acceptance criteria (wrong-checkout submission rejected before tracker/queue/worktree mutation, correct submissions still integrate, malformed queue rows cannot rewrite a registered worktree) are covered.
---
author: oompah
created: 2026-07-30 13:48
---
Harden task submission branch validation: reject wrong-checkout submits before mutating tracker/queue/worktree, and fail-closed on branch mismatch in ProjectStore._reset_existing_worktree and execute_integration. Adds validate_submission_branch used by both the ACP direct-submit path and the HTTP submit endpoint, and covers regression scenarios (wrong-checkout ACP+HTTP rejection with unchanged queue, correct submission still enqueues, worktree preparation refuses to reset a divergent registered worktree, executor returns branch_mismatch without reset).
---
author: oompah
created: 2026-07-30 13:49
---
Run #3 [attempt=3, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 18
- Tokens: 37 in / 859 out [896 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 48s
- Log: OOMPAH-576__20260730T134728Z.jsonl
---
author: oompah
created: 2026-07-30 20:52
---
This parentless Ready-to-Integrate record cannot enter the project's require-epic-parent delivery path. OOMPAH-617 is the canonical OOMPAH-587 child carrying commit 6f5a859b2 through integration; keep this record as provenance and do not redispatch it.
---
author: oompah
created: 2026-07-31 02:37
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 02:37
---
YOLO: merged PR #599.
---
author: oompah
created: 2026-07-31 02:37
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 02:37
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 02:40
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: 6f5a859b215c0a9a4744984e89b27e3fe990050d
- origin_main: 4f51721490488c449926130d4e33ffcc8da760e3
- merged_pr: #599 (Merge pull request #599 from lesserevil/OOMPAH-576)
- focused_tests_projects: 88 passed
- focused_tests_integration_executor: 5 passed
- focused_tests_integration_record: 11 passed
- focused_tests_task_handoff: 17 passed
- focused_tests_worker_submission: 4 passed
---
author: oompah
created: 2026-07-31 02:40
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 36, Tool calls: 29
- Tokens: 35 in / 5.2K out [5.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 3s
- Log: OOMPAH-576__20260731T023755Z.jsonl
---
author: oompah
created: 2026-07-31 02:41
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-07-31 02:41
---
Focus: Completion Auditor
---
author: oompah
created: 2026-07-31 02:44
---
Audit PASS — Merged

[REDACTED]

Safe evidence:
- branch_head: 6f5a859b215c0a9a4744984e89b27e3fe990050d
- merged_pr: #599
- merge_commit: 4f51721490488c449926130d4e33ffcc8da760e3
- contains_in_origin_main: yes
- focused_tests_total: 125 passed
- focused_tests_projects: 88 passed
- focused_tests_integration_executor: 5 passed
- focused_tests_integration_record: 11 passed
- focused_tests_task_handoff: 17 passed
- focused_tests_worker_submission: 4 passed
- regression_test: TestExistingWorktreeBranchValidation::test_wrong_branch_refuses_to_reset_registered_task_worktree PASSED
---
<!-- COMMENTS:END -->
