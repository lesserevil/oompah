---
id: OOMPAH-649
type: task
status: Open
priority: null
title: Preserve dirty task worktrees across worker termination and retry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T07:19:33.053515Z'
updated_at: '2026-07-31T07:19:41.988423Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live data-loss reproduction on 2026-07-31: OOMPAH-645's first worker produced and focused-tested 317 lines across terminal_audit_health.py, orchestrator.py, dashboard.html, and three test files; the operator verified those modifications in the managed worktree. The healthy pytest child was then false-stall terminated with cleanup=False at 07:13:42. Before retry launch, managed worktree reflog recorded 'HEAD@{07:14:19}: reset: moving to HEAD'; the second agent started on a clean 1dc3f53e5 tree with no task commit or stash and had to reimplement the work. OOMPAH-644 similarly entered retry after a reset and reconstructed preserved intent. Implementation scope: worker retry preparation must never discard staged, unstaged, or untracked task-owned changes. Before any reset/sync/rebase, detect dirtiness and preserve it durably via a task-scoped recovery commit/ref or equivalent atomic snapshot; preferably reuse the dirty worktree directly when the branch/head authority still matches. A new attempt must receive explicit recovery context and the exact prior filesystem state. Fail closed on snapshot failure and route to Needs Human rather than running reset --hard. Terminal cleanup may remove a worktree only after committed/pushed/merged evidence or an explicit owner-approved disposition. Relevant files: Projects.ensure/create/reset worktree paths, retry dispatch, agent termination cleanup, branch synchronization, recovery metadata, and hygiene classification. Required tests: abrupt worker termination with staged, unstaged, and untracked edits; cleanup=False retry; process restart before retry; base branch advances; snapshot failure; repeated retry idempotency; terminal cleanup; cross-task isolation. Acceptance: an OOMPAH-645-style retry exposes byte-identical prior edits to the next agent with durable recovery evidence, no task work is silently reset, focused worktree/retry tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

