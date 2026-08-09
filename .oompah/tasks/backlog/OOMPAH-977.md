---
id: OOMPAH-977
type: task
status: Backlog
priority: null
title: Keep managed worktree hook paths worktree-local
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T22:45:47.293153Z'
updated_at: '2026-08-09T22:45:47.293153Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Discovered during OOMPAH-976 branch hygiene after aggressive pruning: the shared repository .git/config retained core.hooksPath=/home/shedwards/.oompah/worktrees/oompah/OOMPAH-858/.oompah-no-hooks after that worktree was removed. ProjectStore._disable_worktree_hooks invokes git config core.hooksPath without --worktree even though extensions.worktreeConfig is enabled, so every task worktree overwrites one shared hook path; pruning the last writer disables commit hooks for main and every surviving worktree. Implementation scope: configure each managed checkout's core.hooksPath in its worktree config, safely migrate only legacy shared Oompah .oompah-no-hooks values, preserve main/pre-commit hooks and the canonical prepare-commit-msg hook, and keep concurrent worktree creation/removal isolated. Relevant code: oompah/projects.py hook installation/worktree creation and tests/test_projects.py/tests/test_commit_hook.py. Required tests: two linked task worktrees retain distinct valid hook paths; pruning either does not break the other or main; legacy shared stale value migrates safely; unrelated operator-configured shared hook path is not erased; canonical trailer hook remains executable/effective. Acceptance: no surviving checkout references a removed worktree hook directory, focused project/commit-hook suites pass, and local shared configuration is repaired without touching task files.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

