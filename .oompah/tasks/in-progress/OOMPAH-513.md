---
id: OOMPAH-513
type: bug
status: In Progress
priority: 1
title: Fail closed on task writes from a managed code checkout
parent: OOMPAH-511
children: []
blocked_by:
- OOMPAH-512
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T15:16:43.939778Z'
updated_at: '2026-07-28T15:46:41.395251Z'
work_branch: epic-OOMPAH-511
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9d4a430d-c8f7-4795-ac4b-d09a8d5a955b
oompah.work_branch: epic-OOMPAH-511
oompah.task_costs:
  total_input_tokens: 997011
  total_output_tokens: 5585
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 997011
      output_tokens: 5585
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 997011
    output_tokens: 5585
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:46:22.967410+00:00'
---
## Summary

Implementation scope

Add a defensive write policy at the native Markdown tracker boundary so a tracker representing a managed state-branch project cannot commit task mutations on the repository's default/code branch. The check must run before any task file or Git index mutation and must cover create, update, comment, label, archive, and maintenance-driven writes through the common persistence path. Prefer an explicit policy/configuration supplied by the project-aware factory over heuristics. Keep reads available where safe. Preserve legacy standalone operation when no state branch is configured, and preserve the dedicated state-branch worktree/checkpoint path.

Relevant files

oompah/oompah_md_tracker.py, oompah/orchestrator.py/project tracker factory code, state-branch tracker tests, and any tracker protocol/type definitions needed for an explicit read-only or expected-write-branch policy.

Required tests

Using disposable repositories only, reproduce an unscoped/default-branch mutation attempt and assert it fails before the task tree, Git index, HEAD, or remote changes. Cover the configured state-branch success path, every public mutation family through the shared guard, legacy standalone success, and an actionable diagnostic. Run focused native tracker/state-branch tests and make test.

Acceptance criteria

A misrouted managed-project task write cannot create or modify .oompah/tasks, cannot create a commit, and cannot push the default branch; correct state-branch writes still checkpoint; standalone behavior remains compatible; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:37
---
Claimed in the OOMPAH-511 isolated worktree. Implemented a tracker-level fail-closed guard covering all public native task mutation families while preserving explicit standalone/legacy writes and non-task release ledgers.
---
author: oompah
created: 2026-07-28 15:41
---
Completed in commit 6533e235e. The native tracker now rejects unscoped managed task writes before filesystem or Git mutation across create, update, archive, comment, label, parent, dependency, attachment, metadata, raw-body, and external-import operations. Correct state-branch and standalone paths remain covered.
---
author: oompah
created: 2026-07-28 15:41
---
Added a fail-closed native tracker write policy with complete public-mutation regression coverage.
---
author: oompah
created: 2026-07-28 15:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 15:43
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 15:43
---
Understanding: Screening OOMPAH-513 for an existing task covering the same managed-checkout write-guard bug. I will search task records by state-branch/write-policy terminology, inspect full candidate task histories, and either archive this as a confirmed duplicate or hand off with evidence if no duplicate exists. No implementation will be attempted in this focus.
---
author: oompah
created: 2026-07-28 15:45
---
Discovery: Duplicate screening found no confirmed duplicate. OOMPAH-256 covers correct configured state-branch routing, while OOMPAH-512 removes projectless managed-runtime tracker selection; neither supplies OOMPAH-513's separate tracker-boundary rejection of an already-misrouted write. OOMPAH-511 explicitly decomposes these as distinct child scopes. Read-only inspection also confirms pushed commit 6533e235e already contains allow_default_branch_task_writes, the pre-mutation guard, public-mutation coverage, and disposable-repository isolation tests.
---
author: oompah
created: 2026-07-28 15:45
---
Implementation: No code changes were made in the duplicate-investigator focus, as required. The requested implementation is already present in remote commit 6533e235e; this pass only screened scope and inspected that commit.
---
author: oompah
created: 2026-07-28 15:45
---
Verification: Reviewed full task histories for OOMPAH-256, OOMPAH-512, OOMPAH-513, OOMPAH-514, and parent OOMPAH-511, plus the complete relevant diff/stat for 6533e235e. No duplicate was found, and the remote epic commit contains the described guard and tests. No test suite was run in this read-only duplicate-screening focus. Worktree is clean, but local epic-OOMPAH-511 currently points to origin/main at e7f3e9370 while origin/epic-OOMPAH-511 points to the implementation commit 6533e235e; the verification focus must test the remote epic state, not the stale local pointer.
---
author: oompah
created: 2026-07-28 15:46
---
Focus handoff: duplicate_detector

1. Outcome: No confirmed duplicate. OOMPAH-513 is a distinct defense-in-depth child of OOMPAH-511; OOMPAH-256 handles correct state-worktree routing and OOMPAH-512 handles project-scoped runtime resolution, while OOMPAH-513 rejects a misrouted task mutation at the tracker boundary.

2. Evidence: Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for state-branch, managed-checkout, fail-closed, and task-write terms. Read full tracker histories for OOMPAH-256/511/512/513/514. Inspected remote commit 6533e235e, which changes oompah/oompah_md_tracker.py and adds tests/test_managed_tracker_state_branch_guard.py with pre-write coverage for public mutation families, configured state-branch success, standalone behavior, and main/ref isolation.

3. Remaining work/risks: The implementation and prior full-suite result are recorded as complete, but this focus did not run tests. The local epic-OOMPAH-511 ref is clean but stale at e7f3e9370 and tracks origin/main; origin/epic-OOMPAH-511 is 6533e235e. A verifier must safely align/test the remote epic commit without losing work, then close the task if results hold.

4. Recommended next focus: test, for independent focused/full-suite verification and task closure. No further implementation is indicated by duplicate screening.
---
author: oompah
created: 2026-07-28 15:46
---
Agent completed successfully in 183s (1002596 tokens)
---
author: oompah
created: 2026-07-28 15:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 19
- Tokens: 997.0K in / 5.6K out [1.0M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 3s
- Log: OOMPAH-513__20260728T154323Z.jsonl
---
author: oompah
created: 2026-07-28 15:46
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 15:46
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 15:46
---
Focus: Test Engineer
---
<!-- COMMENTS:END -->
