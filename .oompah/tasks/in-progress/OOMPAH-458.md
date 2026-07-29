---
id: OOMPAH-458
type: epic
status: In Progress
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
- merge-conflict
- epic:rebasing
- ci-fix
assignee: null
created_at: '2026-07-28T13:03:46.047976Z'
updated_at: '2026-07-29T16:51:17.865035Z'
work_branch: epic-OOMPAH-458
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/578
review_number: '578'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/578
oompah.review_number: '578'
oompah.work_branch: epic-OOMPAH-458
oompah.target_branch: main
oompah.agent_run_id: 29180c88-0367-44c1-89b3-3ed8ed169d1d
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
<!-- COMMENTS:END -->
