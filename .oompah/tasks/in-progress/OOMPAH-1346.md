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
labels: []
assignee: null
created_at: '2026-08-26T18:43:27.314224Z'
updated_at: '2026-08-26T19:31:17.536128Z'
work_branch: OOMPAH-1346
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
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-1346
  base_branch: epic-OOMPAH-1342
  base_sha: d258fc16b1478ff902139c66cdb3e51fa96d209c
  head_sha: f7c4fc4a89012e7173bb09e6ffd3743fdd32f0d6
  submitted_at: '2026-08-26T19:29:12.982338+00:00'
  updated_at: '2026-08-26T19:29:12.982338+00:00'
oompah.work_branch: OOMPAH-1346
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
author: oompah
created: 2026-08-26 19:29
---
Added bounded age-based retention for cold workflow events, removed scheduler-path VACUUM, documented configuration, and added tests. Focused storage/config suite passes.
---
author: oompah
created: 2026-08-26 19:31
---
Implementation complete under direct owner claim; focused tests pass.
---
<!-- COMMENTS:END -->
