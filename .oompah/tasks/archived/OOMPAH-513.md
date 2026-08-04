---
id: OOMPAH-513
type: bug
status: Archived
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
updated_at: '2026-08-04T16:37:07.240643Z'
work_branch: epic-OOMPAH-511
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 43a504c0-2125-40af-ac4d-7e99aeae6d64
oompah.work_branch: epic-OOMPAH-511
oompah.task_costs:
  total_input_tokens: 997035
  total_output_tokens: 6192
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 997011
      output_tokens: 5585
      cost_usd: 0.0
    opus:
      input_tokens: 24
      output_tokens: 607
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 997011
    output_tokens: 5585
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:46:22.967410+00:00'
  - profile: deep
    model: opus
    input_tokens: 24
    output_tokens: 607
    cost_usd: 0.0
    recorded_at: '2026-07-28T16:02:07.536292+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-7fe958d37549: '2026-08-04T16:37:03.655523+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-513
    target_state: Archived
    evidence_fingerprint: 496e9b108ae923b9c395f7ae515961784c0e3c82537d52faecc566300573aa20
    audit_ids:
    - audit-0342e550bca6
    kind: result
    applied: true
    retired_at: '2026-08-04T16:37:03.655536+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-513
    audit_id: audit-0342e550bca6
    attempt_id: attempt-7fe958d37549
    target_state: Archived
    evidence_fingerprint: 496e9b108ae923b9c395f7ae515961784c0e3c82537d52faecc566300573aa20
    status: Archived
    audit_ids:
    - audit-0342e550bca6
    applied: false
    created_at: '2026-08-04T16:37:03.655554+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0342e550bca6
    project_id: proj-14849f1b
    task_id: OOMPAH-513
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 496e9b108ae923b9c395f7ae515961784c0e3c82537d52faecc566300573aa20
    attempts:
    - version: 1
      attempt_id: attempt-7fe958d37549
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 496e9b108ae923b9c395f7ae515961784c0e3c82537d52faecc566300573aa20
      created_at: '2026-08-04T16:33:13.290559+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T16:33:13.290559+00:00'
      branch_key: epic-OOMPAH-511
      verdict: pass
      completed_at: '2026-08-04T16:37:03.655306+00:00'
      ended_at: '2026-08-04T16:37:03.655306+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T16:24:52.729746+00:00'
    updated_at: '2026-08-04T16:37:03.655306+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-7fe958d37549
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 496e9b108ae923b9c395f7ae515961784c0e3c82537d52faecc566300573aa20
    created_at: '2026-08-04T16:33:13.290559+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T16:33:13.290559+00:00'
    branch_key: epic-OOMPAH-511
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
author: oompah
created: 2026-07-28 15:46
---
Understanding: Test focus will independently verify the pushed fail-closed tracker-boundary guard. I will confirm the worktree is clean, safely align it to origin/epic-OOMPAH-511, inspect behavioral coverage for every public mutation family plus state-branch and standalone paths, prove key regressions fail when the guard is broken, then run focused tests and make test before closing or handing off.
---
author: oompah
created: 2026-07-28 15:49
---
Discovery: Safely fast-forwarded the clean local epic branch from e7f3e9370 to pushed commit 6533e235e. The guard is at OompahMarkdownTracker._prepare_default_branch_for_write before task path resolution/Git sync, with a direct pre-write check for the external-import index; the orchestrator explicitly disables default-branch task writes for its global managed tracker and routes project writes to configured state trackers. The dedicated regression file covers 11 mutation families, a real disposable main/state remote isolation flow, management-scope errors, state writes, and non-task ledgers. Focused result so far: 17 passed.
---
author: oompah
created: 2026-07-28 15:50
---
Implementation: No additional source or test edits were needed in this test focus. Review confirmed commit 6533e235e already supplies behavioral coverage for the requested guard, real Git/remote branch isolation, configured state-branch checkpointing, and legacy standalone behavior (including existing state-branch compatibility tests). I also neutralized the guard in-memory and all 11 mutation regressions failed, demonstrating the tests detect the broken behavior.
---
author: oompah
created: 2026-07-28 15:56
---
Run #1 [attempt=1, profile=deep, role=deep -> Codex/default]
- Turns: 0, Tool calls: 45
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 11s
- Log: OOMPAH-513__20260728T154641Z.jsonl
---
author: oompah
created: 2026-07-28 15:57
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 15:57
---
Focus: Technical Writer
---
author: oompah
created: 2026-07-28 15:57
---
Understanding: Technical Writer focus for OOMPAH-513. The implementation (fail-closed write guard at the native Markdown tracker boundary) is already in place per commit 6533e235e and was verified by the Test Engineer focus (17 tests passing, all 11 mutation families covered). My job is to document this security/correctness behavior so operators, contributors, and future agents understand: (1) what the guard does and why, (2) how to configure it, (3) what error they'll see when it fires. I'll explore the implementation, check existing docs/plans, and write a plans/ design doc covering the mechanism plus any missing inline docstrings.
---
author: oompah
created: 2026-07-28 16:01
---
Verification: Focused guard suite passed 17/17; combined native tracker/state-branch unit, e2e, migration, and guard suites passed 269/269. A mutation check that disabled the guard in-memory produced 11/11 expected regression failures. Full make test then passed: 12,630 passed, 7 skipped (12 warnings) in 278.45s. The first full attempt's sole failure was an ACP test unable to write the sandboxed default agent-log directory; its isolated rerun and the complete rerun passed with OOMPAH_AGENT_LOG_DIR=/tmp. Worktree is clean, diff check passes, and HEAD equals origin/epic-OOMPAH-511 at 6533e235e.
---
author: oompah
created: 2026-07-28 16:01
---
Completion: Independently verified commit 6533e235e delivers the fail-closed managed-checkout write policy and required regressions. Misrouted writes fail before filesystem/Git mutation across all covered public mutation families; configured state-branch checkpointing and standalone operation pass; main/local index/remote isolation is proven with disposable repositories. Focused suites and full make test are green. The clean epic-OOMPAH-511 branch is pushed and now correctly tracks origin/epic-OOMPAH-511.
---
author: oompah
created: 2026-07-28 16:02
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 14
- Tokens: 24 in / 607 out [631 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 2s
- Log: OOMPAH-513__20260728T155706Z.jsonl
---
author: oompah
created: 2026-07-28 16:02
---
Verified fail-closed managed task writes in commit 6533e235e; 269 focused tests and the full 12,630-test suite pass, with mutation testing proving all 11 guard cases fail if the guard is disabled.
---
author: oompah
created: 2026-08-04 16:24
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 16:33
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 16:33
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
