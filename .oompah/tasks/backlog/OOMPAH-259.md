---
id: OOMPAH-259
type: task
status: Backlog
priority: null
title: Implement resumable migration of existing projects to Git state branches
parent: OOMPAH-253
children: []
blocked_by:
- OOMPAH-256
labels: []
assignee: null
created_at: '2026-07-20T16:30:00.848090Z'
updated_at: '2026-07-20T16:30:46.729672Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Scope

Provide an explicit operator-driven migration path for existing native Markdown managed projects whose .oompah task tree currently lives on main. Migration must preserve task files and history, avoid interfering with code branches, and be safe to resume or roll back.

Implementation requirements

- Add a supported migration command or UI action that performs preflight validation, creates or validates the target state branch, copies the canonical .oompah task tree, commits/pushes it, verifies the remote result, and only then enables the project state-branch configuration.
- Never delete .oompah history from main automatically. The initial migration must retain main history for rollback and auditability; document optional later cleanup as a separate, explicit operator decision.
- Make migration idempotent and resumable after interruption. Record enough Git-backed migration metadata to detect completed steps without a separate database.
- Provide a rollback command or documented operation that restores legacy configuration when state-branch validation fails, without overwriting either branch.
- Block or clearly serialize concurrent tracker writes during the cutover and surface progress/errors to the operator.

Tests

- End-to-end fixture migrates a project with task files, comments, dependencies, merged tasks, and active code branches; verify all tracker data remains readable after cutover.
- Interrupted migration tests at each stage prove retry is safe and does not duplicate or lose tasks.
- Rollback test proves legacy main-based tracker access is restored and state-branch data is retained.
- Concurrent-write test proves cutover cannot silently lose a mutation.

Acceptance criteria

- An operator can migrate an existing project without manually editing task files.
- After migration, routine task updates no longer modify main.
- Migration is recoverable, auditable, and documented.
- make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

