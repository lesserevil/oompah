---
id: OOMPAH-567
type: task
status: In Progress
priority: null
title: Install complete test dependencies in fresh Makefile worktrees
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T22:48:39.126282Z'
updated_at: '2026-07-29T22:49:16.762221Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fresh integration worktrees run the configured quality gate via make test. The Makefile test target currently depends on setup, which installs only .[server]; uv then adds only the dependency-group pytest packages, leaving the claude, codex, and granian test dependencies absent. Live reproduction on OOMPAH-564 and OOMPAH-565: both exact combined-tree gates produced 112 failures and 4 errors, including SDK install guards and authority/terminal interface tests, while the same heads pass CI where .[dev] is installed. Scope: give make test/test-serial an idempotent test-specific setup marker that installs .[dev] without changing production start/setup behavior; ensure the marker is invalidated by pyproject.toml; document target behavior if needed. Add Makefile/packaging regression tests that prove test targets depend on the complete dev extra and server startup remains server-only. Acceptance criteria: a clean worktree with no preexisting .venv can run make test with both agent SDKs and granian importable; focused tests pass; the full Makefile gate passes; committed work is pushed and submitted through oompah.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 22:49
---
Implementing the fresh-worktree Makefile test dependency fix directly from the primary checkout.
---
<!-- COMMENTS:END -->
