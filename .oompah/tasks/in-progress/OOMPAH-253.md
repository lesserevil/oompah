---
id: OOMPAH-253
type: task
status: In Progress
priority: null
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
blocked_by: []
labels:
- epic:rebasing
assignee: null
created_at: '2026-07-20T16:29:00.780109Z'
updated_at: '2026-07-20T16:48:25.621212Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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

