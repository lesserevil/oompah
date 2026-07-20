---
id: OOMPAH-260
type: task
status: Backlog
priority: null
title: Validate state-branch workflow end to end and publish migration readiness guide
parent: OOMPAH-253
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-20T16:30:27.106890Z'
updated_at: '2026-07-20T16:30:27.106890Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

