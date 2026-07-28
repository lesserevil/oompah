---
id: OOMPAH-513
type: bug
status: Backlog
priority: 1
title: Fail closed on task writes from a managed code checkout
parent: OOMPAH-511
children: []
blocked_by:
- OOMPAH-512
labels: []
assignee: null
created_at: '2026-07-28T15:16:43.939778Z'
updated_at: '2026-07-28T15:17:19.456282Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

Add a defensive write policy at the native Markdown tracker boundary so a tracker representing a managed state-branch project cannot commit task mutations on the repository's default/code branch. The check must run before any task file or Git index mutation and must cover create, update, comment, label, archive, and maintenance-driven writes through the common persistence path. Prefer an explicit policy/configuration supplied by the project-aware factory over heuristics. Keep reads available where safe. Preserve legacy standalone operation when no state branch is configured, and preserve the dedicated state-branch worktree/checkpoint path.

Relevant files

oompah/oompah_md_tracker.py, oompah/orchestrator.py/project tracker factory code, state-branch tracker tests, and any tracker protocol/type definitions needed for an explicit read-only or expected-write-branch policy.

Required tests

Using disposable repositories only, reproduce an unscoped/default-branch mutation attempt and assert it fails before the task tree, Git index, HEAD, or remote changes. Cover the configured state-branch success path, every public mutation family through the shared guard, legacy standalone success, and an actionable diagnostic. Run focused native tracker/state-branch tests and make test.

Acceptance criteria

A misrouted managed-project task write cannot create or modify .oompah/tasks, cannot create a commit, and cannot push the default branch; correct state-branch writes still checkpoint; standalone behavior remains compatible; all tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

