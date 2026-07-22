---
id: OOMPAH-409
type: task
status: Backlog
priority: null
title: Allow Codex conflict resolvers to write shared git metadata
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T15:36:41.250138Z'
updated_at: '2026-07-22T15:36:41.250138Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix the Codex ACP workspace-write sandbox for git worktrees. Conflict resolver agents can write the per-worktree git metadata directory but git rebase/fetch also needs locks in the shared common .git directory; this currently yields read-only filesystem errors and agents exit without resolving PRs. Grant only the resolved common git directory in addition to per-worktree metadata, with safe path validation and tests. Acceptance criteria: worktree-backed Codex CLI sessions receive both required writable git metadata paths; a resolver can execute rebase/fetch without sandbox read-only lock failures; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

