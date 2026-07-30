---
id: OOMPAH-591
type: task
status: Backlog
priority: 1
title: Reconcile the pending audit backlog and stale In Validation tasks
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T14:14:26.620047Z'
updated_at: '2026-07-30T14:14:26.620047Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope

After provider validation and retry behavior land, run an idempotent recovery over existing pending terminal-audit metadata. Requeue eligible requests, supersede only stale evidence revisions, and reconcile OOMPAH-580 and OOMPAH-582 plus every other stale In Validation task without direct task-file edits or unsafe terminal overrides. Add bounded batch/restart behavior if the existing reconciler cannot drain the backlog safely.

Tests

Use persisted metadata fixtures for multi-request tasks, stale fingerprints, already-completed audits, restart midway, and repeated recovery passes. Run focused recovery tests and make test.

Acceptance criteria

Pending audit count reaches zero or every remainder has a specific actionable terminal failure; OOMPAH-580 and OOMPAH-582 leave In Validation correctly; no successful audit is duplicated or overwritten.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

