---
id: OOMPAH-458
type: epic
status: Needs CI Fix
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
updated_at: '2026-07-29T17:43:58.983312Z'
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
  total_input_tokens: 58356
  total_output_tokens: 51120
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 58356
      output_tokens: 51120
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
<!-- COMMENTS:END -->
