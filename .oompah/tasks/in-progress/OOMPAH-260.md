---
id: OOMPAH-260
type: task
status: In Progress
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
updated_at: '2026-07-20T21:05:59.658295Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: d83e7a65-07af-407b-8d1e-49bab6a37743
oompah.task_costs:
  total_input_tokens: 12
  total_output_tokens: 3452
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 12
      output_tokens: 3452
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 12
    output_tokens: 3452
    cost_usd: 0.0
    recorded_at: '2026-07-20T21:03:54.898922+00:00'
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
<!-- COMMENTS:END -->
