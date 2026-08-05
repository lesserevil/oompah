---
id: OOMPAH-458
type: epic
status: In Validation
priority: 0
title: Dispatch independent auditor agents and evaluate target-specific evidence
parent: null
children:
- OOMPAH-468
- OOMPAH-469
- OOMPAH-470
- OOMPAH-471
- OOMPAH-472
- OOMPAH-473
- OOMPAH-474
- OOMPAH-475
blocked_by:
- OOMPAH-457
labels:
- epic:rebasing
- ci-fix
assignee: null
created_at: '2026-07-28T13:03:46.047976Z'
updated_at: '2026-08-05T18:21:54.095226Z'
work_branch: epic-OOMPAH-458
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/578
review_number: '578'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/578
oompah.review_number: '578'
oompah.work_branch: epic-OOMPAH-458
oompah.target_branch: main
oompah.agent_run_id: 1563cbff-136b-43bc-bf80-dc4c160ad62c
oompah.task_costs:
  total_input_tokens: 58402
  total_output_tokens: 61008
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 58402
      output_tokens: 61008
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 184
    output_tokens: 50409
    cost_usd: 0.0
    recorded_at: '2026-07-29T16:53:25.126439+00:00'
  - profile: deep
    model: opus
    input_tokens: 58172
    output_tokens: 711
    cost_usd: 0.0
    recorded_at: '2026-07-29T17:41:44.972023+00:00'
  - profile: deep
    model: opus
    input_tokens: 46
    output_tokens: 9888
    cost_usd: 0.0
    recorded_at: '2026-07-29T17:45:35.844289+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-54e0c72206d5
    project_id: proj-14849f1b
    task_id: OOMPAH-458
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: da0b8ad8f8a7c5d3a56b5cb91e5bcb7e15fd228fd8e21e6949ce1f3108aac4cc
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T18:21:46.172941+00:00'
  attempt_history: []
---
## Summary

Goal

Add the reserved auditor focus and the model-selection, evidence, prompt, result-submission, retry, and scheduling machinery that performs terminal audits using a model independent from all models that contributed to the audited revision.

Required behavior

- Auditor selection prefers a different provider and requires a different model. It may use the same provider only when an explicitly different model is provable.
- Epic audits exclude every recorded contributing provider/model, respect the project provider whitelist, and fail closed when no independent candidate remains.
- Auditor agents are read-only with respect to source, Git history, reviews, and task status. They may inspect files, run tests, and submit one structured verdict through an auditor-only tool.
- Done audits verify completion and acceptance criteria; Merged audits verify correct target landing; Archived audits verify safe retirement.
- Auditors consume ordinary global concurrency, use a priority audit lane, and serialize with workers sharing the same task or epic branch.
- Transient failures rotate candidates and retry; exhausted candidates produce actionable Needs Human instructions.

Constraints

Build on the terminal-audit coordinator epic. Do not let the auditor directly set status, commit, push, merge, or create repair work. Persist safe provider/model identifiers but never credentials or full untrusted model output. All code changes require tests.

Acceptance criteria

A persisted In Validation request can be recovered after restart, dispatched to an eligible independent auditor, evaluated against a stable evidence fingerprint, and completed through the coordinator. Multi-provider, multi-model, epic, retry, and no-candidate scenarios are covered by tests and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 18:10
---
Queued for execution. Every child explicitly depends on OOMPAH-457, so no epic-OOMPAH-458 branch/worktree will be created until OOMPAH-457 has landed. Its first dispatch will therefore branch from the then-latest main.
---
author: oompah
created: 2026-07-29 16:27
---
Branch quality gate passed for `ce2f2b642a69686b120a900467d3d4f0929afd93` using `make test` in 70.9s. Review creation may proceed.
---
author: oompah
created: 2026-07-29 16:27
---
YOLO: Merge conflict detected on MR #578. Rebase `epic-OOMPAH-458` onto main and resolve conflicts.
---
author: oompah
created: 2026-07-29 16:27
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-29 16:27
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-07-29 16:28
---
Understanding: Rebase merge-conflict resolution. Branch epic-OOMPAH-458 has 21 commits since merge-base e9681a5, main has 25 new commits. Plan: fetch origin/main, rebase onto it, resolve conflicts preserving intent from both sides, run focused tests, force-push with lease.
---
author: oompah
created: 2026-07-29 16:30
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-458`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `error`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
No existing worktree matched the review branch tip. Recreate the task worktree before retrying.
```
---
author: oompah
created: 2026-07-29 16:46
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-458`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `error`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
No existing worktree matched the review branch tip. Recreate the task worktree before retrying.
```
---
author: oompah
created: 2026-07-29 16:47
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-458`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `error`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
No existing worktree matched the review branch tip. Recreate the task worktree before retrying.
```
---
author: oompah
created: 2026-07-29 16:52
---
Branch quality gate passed for `c8f3be6769a1614486951a9932d9954aaeb7bc1a` using `make test` in 72.8s. Review creation may proceed.
---
author: oompah
created: 2026-07-29 16:52
---
Rebase conflicts resolved. 21 commits rebased onto origin/main. Merged HEAD+branch changes across acp_agent.py, acp_backends/{base,codex,opencode}.py, acp_tools.py, api_agent.py, orchestrator.py, models.py. Preserved both: task_identifier/action_policy/task_handoff_token/read_only from main and focus/auditor/audit_target/audit_result_handler from branch. Focused tests pass: 137 auditor tests + 383 acp/api/authority + 159 dispatch/duplicate detection.
---
author: oompah
created: 2026-07-29 16:53
---
Verification: focused tests pass on the rebased branch. Force-pushed epic-OOMPAH-458 to origin. All 21 branch commits preserved on top of origin/main (7b7341201). Merge conflicts resolved: acp_agent, acp_backends/{base,codex,opencode}, acp_tools, api_agent, orchestrator, models. Ready for review.
---
author: oompah
created: 2026-07-29 16:53
---
Rebased epic-OOMPAH-458 onto origin/main. Resolved conflicts across acp_agent.py, acp_backends/{base,codex,opencode}.py, acp_tools.py, api_agent.py, orchestrator.py, and models.py by combining main's task_identifier/action_policy/task_handoff_token/read_only additions with the branch's auditor focus/audit_target/audit_result_handler additions. 21 original commits preserved. Focused tests (137 auditor + 383 acp/api/authority + 159 dispatch) pass. Force-pushed to origin.
---
author: oompah
created: 2026-07-29 16:53
---
Agent completed successfully in 1545s (50593 tokens)
---
author: oompah
created: 2026-07-29 16:53
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/opus]
- Turns: 236, Tool calls: 178
- Tokens: 184 in / 50.4K out [50.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 25m 45s
- Log: OOMPAH-458__20260729T162743Z.jsonl
---
author: oompah
created: 2026-07-29 16:57
---
Branch quality gate passed for `b17ee5ef5500d9fe61c6a70f985fcd55fbad6fa0` using `make test` in 81.8s. Review creation may proceed.
---
author: oompah
created: 2026-07-29 17:38
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #14)

**State audited:** `Needs CI Fix`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** Recent comment indicates CI is now passing or PR has been merged; safe to reopen for dispatch.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-07-29 17:41
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-29 17:41
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 17:41
---
Agent completed successfully in 21s (58883 tokens)
---
author: oompah
created: 2026-07-29 17:41
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Codex/gpt-5.6-sol]
- Turns: 1, Tool calls: 1
- Tokens: 58.2K in / 711 out [58.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 21s
- Log: OOMPAH-458__20260729T174125Z.jsonl
---
author: oompah
created: 2026-07-29 17:42
---
YOLO: CI tests failed on MR #578. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-29 17:42
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-29 17:42
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-29 17:44
---
Understanding: CI failure on Python 3.12 (test_poll_does_not_create_duplicate_when_task_is_corrupt). Root cause: the test calls poll_github_issue_intake_project without monkeypatching _github_tracker_for_project, so it makes a real HTTP request to https://api.github.com/repos/example-org/app/issues. Locally that request errors with a generic exception (returned as 0), but in CI GitHub returns 403 rate-limited, which raises TrackerAuthError — which poll re-raises. Fix: add monkeypatch to the failing test to inject the FakeGitHubTracker, matching the pattern used by every other poll-based test in this file.
---
author: oompah
created: 2026-07-29 17:44
---
Implementation: added monkeypatch fixture to test_poll_does_not_create_duplicate_when_task_is_corrupt in tests/test_github_intake_bridge.py that swaps _github_tracker_for_project for a lambda returning the existing FakeGitHubTracker instance — same pattern used by every other poll-based test in this module. Verification: 56/56 tests in test_github_intake_bridge.py pass locally on Python 3.12. Commit 7a3538f09 pushed to epic-OOMPAH-458.
---
author: oompah
created: 2026-07-29 17:45
---
CI fix: added monkeypatch to test_poll_does_not_create_duplicate_when_task_is_corrupt to inject FakeGitHubTracker so the poll no longer calls real api.github.com (rate-limited 403 -> TrackerAuthError on Py3.12 CI). 56/56 tests in test_github_intake_bridge.py pass locally. Commit 7a3538f09.
---
author: oompah
created: 2026-07-29 17:45
---
Agent completed successfully in 204s (9934 tokens)
---
author: oompah
created: 2026-07-29 17:45
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/opus]
- Turns: 54, Tool calls: 40
- Tokens: 46 in / 9.9K out [9.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 24s
- Log: OOMPAH-458__20260729T174213Z.jsonl
---
author: oompah
created: 2026-07-29 17:46
---
Branch quality gate passed for `7a3538f09f994fe08c4e04688ae36e5cbef62727` using `make test` in 70.7s. Review creation may proceed.
---
author: oompah
created: 2026-07-29 17:51
---
YOLO: merged PR #578.
---
<!-- COMMENTS:END -->
