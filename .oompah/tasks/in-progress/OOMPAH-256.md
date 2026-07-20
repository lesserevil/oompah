---
id: OOMPAH-256
type: task
status: In Progress
priority: null
title: Make the native Markdown tracker read and write the configured state branch
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-255
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-20T16:29:29.498883Z'
updated_at: '2026-07-20T17:38:52.677225Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 55d57ed6-69eb-4827-9005-94f770d09bc3
oompah.task_costs:
  total_input_tokens: 18
  total_output_tokens: 5148
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 18
      output_tokens: 5148
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 18
    output_tokens: 5148
    cost_usd: 0.0
    recorded_at: '2026-07-20T17:38:42.081547+00:00'
---
## Summary

Scope

Extend the native Markdown tracker so a project configured with a state branch reads task files from that branch and commits task mutations only there. Code repository operations, PR branches, main, and release branches must remain independent. Preserve the legacy default-branch tracker behavior when no state branch is configured.

Implementation requirements

- Create or reuse a safe dedicated Git worktree or equivalent branch-scoped repository access for the configured state branch; do not switch the shared code checkout between branches.
- Initialize a missing configured state branch only through the explicit bootstrap or migration flow. Normal reads must not create remote branches.
- Route all tracker reads, task writes, comments, status changes, dependencies, and task discovery through the state-branch worktree after migration.
- Keep project code Git operations and state-branch writes isolated with clear locks and error handling.
- Implement pull/rebase/push conflict recovery that never uses destructive reset and provides an actionable error when recovery is impossible.

Tests

- Integration fixture with distinct main and oompah/state branches proves tracker reads and writes use state while code main remains byte-for-byte unchanged.
- Legacy fixture without state-branch configuration proves existing behavior is unchanged.
- Concurrency test covers simultaneous code fetch/rebase activity and a tracker write.
- Failure tests cover missing branch, authentication failure, and non-fast-forward state-branch push without corrupting task data.

Acceptance criteria

- Task mutations for a migrated project create commits only on its configured state branch.
- Code branch heads are not changed by normal native tracker operations.
- Legacy projects continue to work without migration.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-20 17:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-20 17:36
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-20 17:36
---
Understanding: As Duplicate Investigator, I am screening OOMPAH-256 ('Make the native Markdown tracker read and write the configured state branch') for duplicates before any implementation begins. I will search existing tasks for similar topics: state branch, native markdown tracker branch isolation, git worktree tracker, and related keywords.
---
author: oompah
created: 2026-07-20 17:38
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-256 is a unique, non-duplicated task.

**Evidence reviewed:**
- Searched all .oompah/tasks/ directories (open, in-progress, in-review, done, archived) for keywords: state branch, state_branch, StateBranch, native markdown tracker, oompah_md, tracker branch, worktree tracker
- Reviewed all 8 sibling tasks in the OOMPAH-253 epic (255, 256, 257, 258, 259, 260, plus parent 253 and blocker 254)
- Checked archived tasks OOMPAH-266, OOMPAH-264 which reference state-branch but are distinct: OOMPAH-266 ('Do not auto-file epic rebase tasks for tracker-only main divergence') was archived as superseded by OOMPAH-253 — different scope (suppression of rebase tasks, not tracker read/write routing); OOMPAH-264 similar suppression scope

**Closest reviewed tasks (all confirmed distinct):**
- OOMPAH-255 (Done): adds project model fields for state branch configuration — distinct: config model only, not tracker routing
- OOMPAH-257 (Open, blocked by 256): checkpoint coalescing after state-branch support — distinct: write coalescing, not read/write routing
- OOMPAH-258 (Open, blocked by 256): bootstrap and docs — distinct: new project setup only
- OOMPAH-259 (Open, blocked by 256+257): migration of existing projects — distinct: migration path only
- OOMPAH-260 (Open): E2E validation — distinct: integration testing only

**Design artefacts available:** plans/state-branch-design.md, docs/state-branch-migration.md (created by OOMPAH-254 agent), plans/multi-branch-support.md

**Remaining work:** Full implementation of state-branch-aware reads/writes in the native Markdown tracker using a dedicated git worktree, including isolation from code branches, conflict recovery, and the required test suite (integration fixtures, legacy compat, concurrency, and failure tests).

**Recommended next focus:** feature (backend implementation of git-worktree-based tracker routing, isolation locks, conflict recovery, and tests)
---
author: oompah
created: 2026-07-20 17:38
---
Agent completed successfully in 120s (5166 tokens)
---
author: oompah
created: 2026-07-20 17:38
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 34, Tool calls: 23
- Tokens: 18 in / 5.1K out [5.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 0s
- Log: OOMPAH-256__20260720T173647Z.jsonl
---
<!-- COMMENTS:END -->
