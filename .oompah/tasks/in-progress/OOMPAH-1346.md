---
id: OOMPAH-1346
type: task
status: In Progress
priority: 1
title: Bound workflow history and workspace storage growth
parent: OOMPAH-1342
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-26T18:43:27.314224Z'
updated_at: '2026-08-26T18:57:01.318138Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: manual-service-recovery-20260826-storage
  request_fingerprint: 6f66fb1566bdbad6da13f55ff0f2452ac19762cc3b8a1311af536d410e883581
oompah.lifecycle_revision: 2
---
## Summary

Implement workstream 4 of plans/service-throughput-recovery.md. Add configurable retention/compaction for workflow_job_events_archive, log rotation, pytest temporary roots, and safe removal of build products in terminal worktrees. Cleanup must preserve active, dirty, unmerged, audit-protected, and shared-owner artifacts; use bounded batches/time budgets and expose metrics/dry-run diagnostics. Never run an unbounded SQLite VACUUM on the scheduler path. Add unit and integration tests for retention, protected-artifact safety, restart interruption, and bounded runtime. Acceptance: historical event growth is capped and production cleanup can reclaim inactive Cargo target trees without affecting recoverable work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-26 18:57
---
Direct implementation ownership assigned to the current manual recovery session (owner claim: shedwards). The project is paused and the human-only fence is present; do not dispatch this task to an autonomous worker.
---
<!-- COMMENTS:END -->
