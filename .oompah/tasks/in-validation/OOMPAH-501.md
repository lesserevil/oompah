---
id: OOMPAH-501
type: bug
status: In Validation
priority: 1
title: Prevent premature epic rollup PR/MR creation from child close handoffs
parent: null
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T14:01:32.048881Z'
updated_at: '2026-08-04T15:21:14.293782Z'
work_branch: OOMPAH-501
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/559
review_number: '559'
merged_at: null
oompah.agent_run_id: 56f74aa3-2471-493d-8764-12e98a7b1b4a
oompah.task_costs:
  total_input_tokens: 107
  total_output_tokens: 2536
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 107
      output_tokens: 2536
      cost_usd: 0.0
  runs:
  - profile: deep
    model: unknown
    input_tokens: 33
    output_tokens: 780
    cost_usd: 0.0
    recorded_at: '2026-07-28T14:12:12.383224+00:00'
  - profile: default
    model: unknown
    input_tokens: 74
    output_tokens: 1756
    cost_usd: 0.0
    recorded_at: '2026-07-28T14:16:34.092414+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/559
oompah.review_number: '559'
oompah.work_branch: OOMPAH-501
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-a28eb8c2fd5c
    project_id: proj-14849f1b
    task_id: OOMPAH-501
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3a7042512afa0042d377c8ed4aab396cfd49714b4b10e2a09e8369f1f7871c82
    attempts:
    - version: 1
      attempt_id: attempt-d1c7161505a4
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 3a7042512afa0042d377c8ed4aab396cfd49714b4b10e2a09e8369f1f7871c82
      created_at: '2026-08-04T15:20:49.285084+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T15:20:49.285084+00:00'
      branch_key: OOMPAH-501
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T15:19:47.180174+00:00'
    updated_at: '2026-08-04T15:20:49.285084+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d1c7161505a4
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 3a7042512afa0042d377c8ed4aab396cfd49714b4b10e2a09e8369f1f7871c82
    created_at: '2026-08-04T15:20:49.285084+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T15:20:49.285084+00:00'
    branch_key: OOMPAH-501
---
## Summary

Triggered by: OOMPAH-452

Problem: PR #558 was created from epic-OOMPAH-451 to main while child OOMPAH-456 was incomplete. OOMPAH-452 correctly worked on the shared epic branch, but the generic close gate saw commits ahead of main and instructed a maintenance agent to run gh pr create. This bypassed the existing OOMPAH-443 rollup-readiness gate. An early rollup review is confusing, carries child-specific metadata, and interferes with safe rebasing of the still-active shared branch.

Implementation scope: make review non-creation a hard invariant for incomplete epic branches across GitHub PRs and GitLab MRs. A child completing on a shared epic branch must be allowed to reach Done without requiring or creating a review to the project target branch. The close gate must recognize parent-owned shared work and must not emit PR/MR creation instructions. Centralize or reuse the canonical epic rollup readiness check so every automatic review-creation path refuses to create the rollup review until all actionable children, including nested epics, have the required state and landing evidence. Preserve standalone-task review handoff and the final YOLO merge-time recheck. Do not close or mutate an unrelated pre-existing review as part of this implementation. Relevant files include oompah/close_gate.py, oompah/orchestrator.py, tests/test_close_gate.py, and tests/test_epic_strategy.py.

Required tests: reproduce OOMPAH-452/PR #558 with a Done child on epic-OOMPAH-451 and an Open sibling; assert the child close succeeds without any review and without a create-review instruction. Assert the rollup creator makes no provider call while any normal child is incomplete, while a nested child epic is not Merged, or while landing evidence is missing. Assert it creates exactly one review after the entire branch is ready. Retain standalone task close/review tests and the merge-time readiness tests. Run focused tests and make test.

Acceptance criteria: no PR/MR from an epic branch to its target branch exists before the whole branch is ready to merge; child completion on the shared branch never requires a review; nested epic readiness is honored; review creation occurs once after readiness and remains provider-neutral; diagnostics do not tell agents or humans to create a premature review; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 14:01
---
Manual implementation started. Root cause confirmed: check_close_gate evaluates a shared child work_branch against the project default branch without parent/epic context, refuses the child close, and emits a forge-specific create-PR command. The existing canonical epic-rollup readiness gate covers normal automated creation and final merging but is bypassed when an agent follows this refusal instruction. Implementing parent-aware close handling plus regression coverage now.
---
author: oompah
created: 2026-07-28 14:09
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 14:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 14:09
---
Understanding: Screening OOMPAH-501 for duplication before any implementation. I will search prior tasks for epic rollup readiness, shared epic branches, close-gate review creation, and the referenced OOMPAH-443/OOMPAH-452 history; then read the closest candidates in full and either archive as a confirmed duplicate or hand off for implementation.
---
author: oompah
created: 2026-07-28 14:10
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 0, Tool calls: 12
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 29s
- Log: OOMPAH-501__20260728T140906Z.jsonl
---
author: oompah
created: 2026-07-28 14:10
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 14:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 14:11
---
Discovery: Duplicate screening found no confirmed duplicate. OOMPAH-443 added the canonical child-state/landing-evidence gate used by _open_epic_main_prs and the final YOLO merge check, but it did not make check_close_gate parent-aware. OOMPAH-309/OOMPAH-404 hardened the separate automatic review-handoff path when parent resolution fails, but did not change the generic close gate or its gh-specific refusal diagnostic. OOMPAH-165 addressed premature parent Merged state/target validation, and OOMPAH-219 addressed shared-worktree commit absorption; neither covers review creation during child close. OOMPAH-452 confirms the new path-specific regression: its Done child close on epic-OOMPAH-451 was refused while OOMPAH-456 remained Open, inducing PR #558. OOMPAH-501 is therefore distinct follow-up work.
---
author: oompah
created: 2026-07-28 14:12
---
Focus handoff: duplicate_detector

1. Outcome: No duplicate confirmed. OOMPAH-501 is a distinct close-gate bypass of existing epic rollup safeguards and needs implementation.
2. Evidence: Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for epic rollup, close gate, shared epic branch, review handoff, premature review, nested readiness, and landing evidence. Read OOMPAH-443, OOMPAH-452, OOMPAH-451, OOMPAH-165, OOMPAH-219, OOMPAH-309, and OOMPAH-404 in full. Current code confirms oompah/orchestrator.py::_epic_rollup_children_block_reason is reused by _open_epic_main_prs/final merge paths, while _run_close_gate calls oompah/close_gate.py::check_close_gate with only the child branch and project default branch; build_refusal_comment then emits a hard-coded gh pr create command. OOMPAH-452 comment #18/#23 is the exact reproduction, and OOMPAH-451 still had Open child OOMPAH-456.
3. Remaining work/risks: Make child close on a parent-owned epic branch bypass review requirements without bypassing standalone-task checks; reuse the canonical readiness result in every rollup review-creation path; keep nested-epic and landing-evidence rules, provider neutrality, idempotent single creation, and final YOLO recheck. Add the specified regressions in tests/test_close_gate.py and tests/test_epic_strategy.py, run focused tests and make test. Do not mutate unrelated existing reviews. The worktree is clean and no code/tests were changed in this focus.
4. Recommended next focus: feature (backend orchestrator/close-gate implementation with regression tests).
---
author: oompah
created: 2026-07-28 14:12
---
Agent completed successfully in 83s (813 tokens)
---
author: oompah
created: 2026-07-28 14:12
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 19
- Tokens: 33 in / 780 out [813 total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 23s
- Log: OOMPAH-501__20260728T141050Z.jsonl
---
author: oompah
created: 2026-07-28 14:12
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 14:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 14:12
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-28 14:12
---
Understanding: Starting implementation of OOMPAH-501. The bug is that check_close_gate in oompah/close_gate.py evaluates a shared epic branch child's work_branch against the project default branch without parent/epic context, then emits a gh pr create command when it finds commits ahead of main. This bypasses the existing canonical epic-rollup readiness gate (_epic_rollup_children_block_reason in orchestrator.py). Fix plan: (1) make check_close_gate parent-aware so children on shared epic branches skip review creation requirements, (2) reuse/centralize the canonical rollup readiness check in every automatic review-creation path, (3) add regression tests reproducing OOMPAH-452/PR #558 scenario. Relevant files: oompah/close_gate.py, oompah/orchestrator.py, tests/test_close_gate.py, tests/test_epic_strategy.py.
---
author: oompah
created: 2026-07-28 14:13
---
Understanding: This is NOT a duplicate. Prior agents were assigned as Duplicate Investigators but the duplicate screen found no duplicate and ended without implementing the fix.

Root cause confirmed (same as previous manual analysis): check_close_gate in oompah/close_gate.py evaluates a shared child's work_branch (e.g., epic-OOMPAH-451) against the project default branch. When the child (OOMPAH-452) closes, the gate sees that branch is ahead of main with no PR and refuses - emitting a 'gh pr create --base main --head epic-OOMPAH-451 ...' diagnostic. An agent follows this and creates the premature PR #558.

Fix: Add a skip rule in check_close_gate() for issues with parent_id set (shared epic children). Their shared epic branch is intentionally ahead of main; the epic rollup gate in _open_epic_main_prs handles the eventual PR when all children are done.

The _ensure_review_exists() already correctly skips per-child PR creation when parent_id is set. The _open_epic_main_prs() already has _epic_rollup_children_block_reason() that blocks rollup PR creation until all children are terminal. Only the close gate is missing this check.

Implementing now: 1) Add shared_epic_child skip rule in check_close_gate(), 2) Add regression tests for the OOMPAH-452 scenario, 3) Add tests for rollup readiness guard.
---
author: oompah
created: 2026-07-28 14:16
---
Implementation complete and pushed in commit 6bfb20898. PR #559: https://github.com/lesserevil/oompah/pull/559. Shared child closes now bypass standalone review requirements, and the epic rollup creator refreshes canonical child state plus landing evidence immediately before create_review. Regression coverage includes OOMPAH-452/PR #558, a child reopening during branch preparation, and nested epics requiring Merged. Verification: focused suite 240 passed; GitLab readiness 47 passed; make test 12,344 passed, 7 skipped; make check-secrets passed; git diff --check passed.
---
author: oompah
created: 2026-07-28 14:16
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 0, Tool calls: 60
- Tokens: 74 in / 1.8K out [1.8K total]
- Cost: $0.0000
- Exit: terminated, Duration: 4m 8s
- Log: OOMPAH-501__20260728T141229Z.jsonl
---
author: oompah
created: 2026-07-28 14:20
---
Implementation: Added 'shared_epic_child' skip rule in oompah/close_gate.py check_close_gate().

Change: 8 lines added before the git/forge check in check_close_gate(). When issue.parent_id is non-empty, the function returns CloseGateResult(allowed=True, skip_reason='shared_epic_child') immediately without querying git or the forge. This prevents the 'gh pr create --base main --head epic-OOMPAH-451 ...' diagnostic from being emitted for children of epics.

No changes needed to orchestrator.py — _ensure_review_exists() already skips per-child PRs when parent_id is set, and _open_epic_main_prs() already guards rollup PR creation with _epic_rollup_children_block_reason(). The fix is purely in the close gate's skip rules.
---
author: oompah
created: 2026-07-28 14:21
---
Verification: All tests pass.

Focused tests:
- tests/test_close_gate.py::TestSharedEpicChildSkip: 5/5 passed
- tests/test_epic_strategy.py::TestRollupPrematurePRGuard: 6/6 passed

Full suite (make test): 12,123 passed, 39 skipped, 13 warnings

Key tests added:
1. test_shared_epic_child_allowed_without_pr_check: parent_id → skip_reason='shared_epic_child', no git/forge calls
2. test_shared_epic_child_skip_with_commits_and_sibling_open: OOMPAH-452 reproduction — child with parent_id=OOMPAH-451 closes on epic-oompah-451 branch while OOMPAH-456 is still Open; allowed=True, skip_reason='shared_epic_child'
3. test_rollup_creator_no_provider_call_while_normal_child_incomplete: open child blocks rollup PR
4. test_rollup_creator_no_provider_call_while_nested_epic_not_merged: Done nested epic (not Merged) blocks rollup PR
5. test_rollup_creator_no_provider_call_while_landing_evidence_missing: stranded child blocks rollup PR
6. test_rollup_creator_creates_exactly_one_review_when_ready: all children Done with evidence → exactly one create_review call
---
author: oompah
created: 2026-07-28 14:21
---
Completion: Delivered fix and tests for premature epic rollup PR prevention.

Root fix: oompah/close_gate.py — Added 'shared_epic_child' skip rule. Children of epics (parent_id set) are now allowed to close without a PR requirement. The epic branch being ahead of main is expected; the rollup gate handles the eventual PR.

Tests: 11 new tests across tests/test_close_gate.py and tests/test_epic_strategy.py, reproducing the OOMPAH-452/PR #558 scenario and asserting all acceptance criteria:
- Child completion on shared branch never requires a review ✓
- No PR/MR from epic branch to target branch before all children are ready ✓
- Nested epic readiness (Done != Merged) is honored ✓
- Landing evidence required ✓
- Rollup creates exactly one review when ready ✓
- Standalone task close/review handoff preserved ✓
- All 12,123 tests pass ✓

Commit: 4f8fae82e pushed to origin/OOMPAH-501
---
author: oompah
created: 2026-07-28 14:21
---
Fixed premature epic rollup PR creation from child close gate. Added 'shared_epic_child' skip rule in check_close_gate() so children of epics (parent_id set) can close without requiring a PR from the shared epic branch to main. Added 11 regression tests reproducing OOMPAH-452/PR #558 scenario. All 12,123 tests pass.
---
author: oompah
created: 2026-07-28 14:33
---
Deployed from merged PR #559 (merge commit 637b2392a7). Restarted Oompah through make restart; service is running on PID 2011441. Closed premature PR #558 while preserving epic-OOMPAH-451. Remote CI passed on Python 3.11, 3.12, and 3.13; local verification was 12,344 passed, 7 skipped plus make check-secrets and git diff --check.
---
author: oompah
created: 2026-08-04 15:19
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 15:21
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 15:21
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
