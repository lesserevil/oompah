---
id: OOMPAH-260
type: task
status: Done
priority: null
title: Validate state-branch workflow end to end and publish migration readiness guide
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-257
- OOMPAH-258
- OOMPAH-259
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-20T16:30:27.106890Z'
updated_at: '2026-07-20T21:22:02.284804Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 168f3920-4837-434c-92a8-7910d678334b
oompah.task_costs:
  total_input_tokens: 67942
  total_output_tokens: 6746
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 67942
      output_tokens: 6746
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 12
    output_tokens: 3452
    cost_usd: 0.0
    recorded_at: '2026-07-20T21:03:54.898922+00:00'
  - profile: default
    model: unknown
    input_tokens: 67816
    output_tokens: 531
    cost_usd: 0.0
    recorded_at: '2026-07-20T21:05:55.904517+00:00'
  - profile: standard
    model: unknown
    input_tokens: 114
    output_tokens: 2763
    cost_usd: 0.0
    recorded_at: '2026-07-20T21:22:01.563170+00:00'
---
## Summary

Scope

Perform the final integration validation for the Git-backed state-branch and checkpoint workflow. Use disposable Git fixtures only; do not migrate live managed projects as part of this task. Publish a concise operator readiness guide covering the tested migration procedure and rollback decision points.

Implementation requirements

- Build an end-to-end test scenario covering bootstrap of a new project, task creation and agent-style updates, checkpoint coalescing, code commits on main, release-branch work, and migration of a legacy fixture project.
- Verify the state branch receives durable task checkpoints while main and release branch histories receive no routine task metadata commits after state-branch enablement.
- Verify direct task reads, dashboard status, orchestration, dependencies, comments, and release-delivery candidate discovery continue to work after migration.
- Exercise a failed state-branch push and migration rollback/retry.
- Add or complete docs/ migration readiness material with preflight checklist, validation commands, rollback criteria, and a recommendation for staged production rollout.

Tests

- Automated end-to-end Git integration test with a bare remote and separate code/state branches.
- Regression assertion on commit histories: expected task checkpoint commits are only on oompah/state after cutover.
- Test a simulated failed push plus recovery.

Acceptance criteria

- The complete workflow is demonstrated in automated tests without an external database or service.
- Operators have a tested staged-rollout and rollback guide.
- No live project migration occurs automatically.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 21:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 21:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 21:03
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-260 is NOT a duplicate of any existing task.

**Evidence reviewed:**
- Searched all .oompah/tasks/ directories (open, in-progress, done, merged, archived) for keywords: state-branch, state_branch, migration readiness, checkpoint workflow, git-backed state, readiness guide, end-to-end validation, oompah/state, validate.*end.to.end
- Read OOMPAH-253 epic and all sibling tasks to compare scope
- Checked OOMPAH-202 (Run end-to-end release delivery migration and regression coverage) — confirmed distinct feature area (release delivery, not state-branch workflow)
- Checked OOMPAH-31 (archived, bootstrap validation) — confirmed distinct scope (1.0 CLI bootstrap smoke test, not state-branch E2E)

**All sibling tasks in OOMPAH-253 confirmed distinct:**
- OOMPAH-254 (Done): Design documents only — plans/state-branch-design.md + docs/state-branch-migration.md
- OOMPAH-255 (Done): Project model config fields (state_branch_enabled, checkpoint_debounce_ms, etc.)
- OOMPAH-256 (Done): State-branch-aware tracker read/write routing via git worktree
- OOMPAH-257 (Done): Checkpoint coalescing queue with debounce/max-delay timers
- OOMPAH-258 (Done): Project-bootstrap state-branch initialization + operator docs
- OOMPAH-259 (In Progress): Resumable migration of EXISTING projects + rollback — distinct from E2E validation

**Unique scope of OOMPAH-260 (not covered elsewhere):**
1. End-to-end integration test with a bare remote, separate code/state branches, covering: bootstrap, task create+update, checkpoint coalescing, code commits on main, release-branch work, legacy project migration
2. Regression assertion: task checkpoint commits appear ONLY on oompah/state after cutover (main/release branch histories unchanged)
3. Simulated failed push + recovery test
4. Operator readiness guide (docs/) with preflight checklist, validation commands, rollback criteria, staged production rollout recommendation

**Blockers status:** OOMPAH-257 and OOMPAH-258 are Done; OOMPAH-259 is In Progress.

**Key implementation inputs:**
- plans/state-branch-design.md: §5 (checkpoint coalescing), §6 (migration), §7 (API/CLI spec)
- docs/state-branch-migration.md: operator guide skeleton
- oompah/checkpoint_queue.py: coalescing implementation (from OOMPAH-257)
- oompah/project_bootstrap/__init__.py: initialize_state_branch() (from OOMPAH-258)
- oompah/state_branch_migration.py: migration engine (from OOMPAH-259)
- Tests should use bare git repos as fixtures (see tests/test_state_branch_migration.py pattern from OOMPAH-259)

**Recommended next focus:** test (E2E integration tests + docs readiness guide)
---
author: oompah
created: 2026-07-20 21:03
---
Agent completed successfully in 95s (3464 tokens)
---
author: oompah
created: 2026-07-20 21:04
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 25, Tool calls: 16
- Tokens: 12 in / 3.5K out [3.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 35s
- Log: OOMPAH-260__20260720T210226Z.jsonl
---
author: oompah
created: 2026-07-20 21:04
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-20 21:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 21:05
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-20 21:05
---
Agent completed successfully in 26s (68347 tokens)
---
author: oompah
created: 2026-07-20 21:05
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 67.8K in / 531 out [68.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 26s
- Log: OOMPAH-260__20260720T210535Z.jsonl
---
author: oompah
created: 2026-07-20 21:06
---
Agent completed without closing this issue (26s (68347 tokens)). Escalating from 'default' to 'standard'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-20 21:06
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 21:06
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-20 21:09
---
Understanding + plan: Writing end-to-end integration tests for the state-branch workflow (OOMPAH-260).

Key findings:
- All blocker tasks (OOMPAH-257, OOMPAH-258, OOMPAH-259) are done; their individual tests pass (215 tests in 12s).
- Existing test files cover unit-level: migration stages, tracker routing, checkpoint coalescing, bootstrap, project config.
- OOMPAH-260 specifically requires:
  (1) A top-level E2E test file (tests/test_state_branch_e2e.py) covering: new project with bare remote, code commits on main interleaved with task updates, release branch isolation, legacy migration, commit history regression assertions, failed push + recovery.
  (2) Operator readiness guide (docs/state-branch-migration-readiness.md) with preflight checklist, validation commands, rollback criteria, staged rollout recommendation.

Implementation plan:
- tests/test_state_branch_e2e.py: § 1 New project E2E (bare remote), § 2 Legacy migration E2E (Stage A→B), § 3 Commit history regression assertions, § 4 Failed push simulation + recovery, § 5 Release branch isolation, § 6 Orchestration continuity (deps, comments, reads)
- docs/state-branch-migration-readiness.md: Standalone operator readiness guide
- make test pass
---
author: oompah
created: 2026-07-20 21:21
---
Implementation: Added end-to-end tests and operator readiness guide.

Files created:
1. tests/test_state_branch_e2e.py (44 tests, 9 coverage sections)
   - § 1 New project E2E: bare remote, bootstrap, task CRUD, code isolation
   - § 2 Legacy migration E2E: Stage A→B with interleaved code commits
   - § 3 Commit history regression: verifies zero task commits on main/release after cutover
   - § 4 Failed push + recovery: task preserved locally when push fails
   - § 5 Release branch isolation: no task commits on release branches post-cutover; Stage C cleanup
   - § 6 Orchestration continuity: reads, updates, comments, deps, candidate discovery work after migration
   - § 7 Rollback + retry: Stage B rollback, state branch preserved, idempotent re-migration
   - § 8 Pre-migration validation: corrupt YAML, dirty tree, result format
   - § 9 Checkpoint coalescing: 5 mutations → 1 commit, pending counter accuracy

2. docs/state-branch-migration-readiness.md
   - Preflight checklist (environment, repo health, task data, branch protection, timing)
   - Validation commands for each stage
   - Rollback criteria (mandatory, precautionary, expected non-errors)
   - Staged production rollout (Phase 0→4 over 2 months)
   - Quick reference card
   - Test coverage table
---
author: oompah
created: 2026-07-20 21:21
---
Verification: make test passes with 9771 passed, 36 skipped, 0 failed (in 180s).

New E2E test suite specifically:
- 44 tests in tests/test_state_branch_e2e.py: all pass
- 358 total state-branch tests (all modules): all pass

Key regression assertions verified:
- Main branch SHA does not change after state-branch task creation ✓
- Release branch receives no new commits from task mutations ✓  
- 5 coalesced mutations produce exactly 1 git commit on state branch ✓
- Task files preserved locally even when remote push fails ✓
- Stage B rollback restores tasks to main from state branch ✓
- fetch_candidate_issues/fetch_all_issues/add_comment/add_dependency all work after migration ✓

No live project migrations occur — all tests use disposable git fixtures (bare remote + working tree in tmp_path).
---
author: oompah
created: 2026-07-20 21:21
---
Completion: Delivered all acceptance criteria for OOMPAH-260.

✅ Automated E2E tests (tests/test_state_branch_e2e.py, 44 tests) demonstrate the complete workflow without external database or service — uses only bare git repos as fixtures.

✅ Regression assertions confirm task checkpoint commits appear ONLY on oompah/state after cutover; main and release branches receive zero task metadata commits.

✅ Simulated failed push + recovery tested: task data preserved locally when push fails, non-fast-forward recovery via rebase verified.

✅ Operator readiness guide published (docs/state-branch-migration-readiness.md) with:
  - Preflight checklist (12 items across 4 categories)
  - Validation commands for each migration stage
  - Rollback criteria with mandatory/precautionary/expected-behavior distinction
  - 4-phase staged production rollout recommendation (canary → low-risk → active → cleanup)
  - Quick reference card

✅ No live project migration occurs automatically (all tests use tmp_path fixtures).

✅ make test passes: 9771 passed, 36 skipped, 0 failed.
---
author: oompah
created: 2026-07-20 21:21
---
E2E integration tests (44 tests in tests/test_state_branch_e2e.py) and operator readiness guide (docs/state-branch-migration-readiness.md) delivered. All 9771 tests pass. Covers: new project bootstrap, legacy migration, commit history regression, failed push recovery, release branch isolation, orchestration continuity, checkpoint coalescing.
---
<!-- COMMENTS:END -->
