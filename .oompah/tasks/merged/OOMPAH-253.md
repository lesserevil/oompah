---
id: OOMPAH-253
type: task
status: Merged
priority: 0
title: 'Epic: Git-backed Oompah state branches and coalesced metadata checkpoints'
parent: null
children:
- OOMPAH-254
- OOMPAH-255
- OOMPAH-256
- OOMPAH-257
- OOMPAH-258
- OOMPAH-259
- OOMPAH-260
- OOMPAH-261
- OOMPAH-262
- OOMPAH-269
- OOMPAH-271
- OOMPAH-275
- OOMPAH-276
- OOMPAH-277
- OOMPAH-278
- OOMPAH-279
- OOMPAH-280
blocked_by: []
labels:
- epic:rebasing
assignee: null
created_at: '2026-07-20T16:29:00.780109Z'
updated_at: '2026-07-20T21:59:37.183461Z'
work_branch: epic-OOMPAH-253
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/457
review_number: '457'
merged_at: null
oompah.work_branch: epic-OOMPAH-253
oompah.target_branch: main
oompah.agent_run_id: c0e3eb62-030a-44dd-af70-847aad257030
oompah.review_url: https://github.com/lesserevil/oompah/pull/457
oompah.review_number: '457'
oompah.task_costs:
  total_input_tokens: 35
  total_output_tokens: 873
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 35
      output_tokens: 873
      cost_usd: 0.0
  runs:
  - profile: standard
    model: unknown
    input_tokens: 35
    output_tokens: 873
    cost_usd: 0.0
    recorded_at: '2026-07-20T21:28:36.128417+00:00'
---
## Summary

Goal

Reduce metadata churn on managed project code branches while keeping Git as the only durable task-data store and adding no services or applications. Oompah task and epic data must move to a dedicated per-project Git state branch, conventionally oompah/state. Code branches such as main and release/* must no longer receive routine task metadata commits.

Target behavior

- New managed projects created through project-bootstrap are configured for the dedicated state branch from the start.
- Oompah reads and writes native task data on that state branch while code work continues on main and release branches.
- Multiple metadata mutations are coalesced into bounded checkpoint commits; explicit human edits and terminal/critical transitions are flushed immediately.
- Ephemeral runtime telemetry is not committed per event; durable task state and concise focus handoffs remain Git-backed.
- Existing managed projects migrate safely, resumably, and with rollback guidance, without losing task history or blocking code work.

Constraints

- Git remains the sole persistent store. Do not add a database, queue service, daemon, or third-party application.
- Preserve existing project tracker behavior until migration is explicitly completed.
- Preserve auditability: every durable checkpoint is attributable and recoverable from Git history.

Delivery

Implement the child tasks in dependency order. Update operator and bootstrap documentation, add migration tooling, and verify behavior with unit, integration, and end-to-end Git fixtures.

Acceptance criteria

- A migrated project can create, update, read, and orchestrate tasks using its state branch while its main branch remains unchanged by routine metadata updates.
- A newly bootstrapped project has the same behavior by default.
- Existing projects have a documented, tested migration and rollback path.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 21:23
---
The epic branch `epic-OOMPAH-253` is stale: it has fallen behind `main`. Rebase the branch onto `origin/main`, resolve any conflicts, and force-push with `git push --force-with-lease`.
---
author: oompah
created: 2026-07-20 21:23
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-20 21:23
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-07-20 21:23
---
Understanding: My role is Merge Conflict Resolver. The branch epic-OOMPAH-253 has fallen behind main and needs to be rebased onto origin/main with all conflicts resolved. I will: (1) fetch origin, (2) rebase onto origin/main, (3) resolve all conflicts preserving intent from both sides, (4) run tests, (5) force-push with --force-with-lease.
---
author: oompah
created: 2026-07-20 21:24
---
Discovery: The branch epic-OOMPAH-253 is 17 commits ahead of the merge base with main, which is 34 commits ahead. The main branch changes are entirely .oompah/tasks/ metadata files (task updates for OOMPAH-253, OOMPAH-260, OOMPAH-280). The epic branch has significant code changes across oompah/ source files. Expected conflicts: .oompah/tasks/done/OOMPAH-280.md and OOMPAH-253.md (different paths on each side). Starting rebase now.
---
author: oompah
created: 2026-07-20 21:27
---
Implementation: Rebased epic-OOMPAH-253 onto origin/main successfully. git rebase detected 9 metadata commits that were already cherry-picked into main (skipped without conflict), then cleanly applied all 8 code commits (OOMPAH-254 through OOMPAH-260). No merge conflicts required manual resolution — both sides only touched task metadata files that were already in sync.
---
author: oompah
created: 2026-07-20 21:28
---
Verification: make test passed — 9771 passed, 36 skipped, 13 warnings in 181s. No test failures introduced by the rebase.
---
author: oompah
created: 2026-07-20 21:28
---
Completion: Merge conflict resolution complete. Branch epic-OOMPAH-253 successfully rebased onto origin/main and force-pushed. The branch now has 8 code commits cleanly on top of main (OOMPAH-254 through OOMPAH-260). All 9771 tests pass. No code changes beyond conflict resolution were made.
---
author: oompah
created: 2026-07-20 21:28
---
Rebased epic-OOMPAH-253 onto origin/main, resolved all conflicts (none required manual intervention — metadata commits were already in sync), force-pushed with --force-with-lease. All 9771 tests pass.
---
author: oompah
created: 2026-07-20 21:28
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 0, Tool calls: 21
- Tokens: 35 in / 873 out [908 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 23s
- Log: OOMPAH-253__20260720T212318Z.jsonl
---
<!-- COMMENTS:END -->
