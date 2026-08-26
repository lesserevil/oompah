---
id: OOMPAH-1346
type: task
status: Ready to Integrate
priority: 1
title: Bound workflow history and workspace storage growth
parent: OOMPAH-1342
children: []
blocked_by:
- OOMPAH-1345
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-26T18:43:27.314224Z'
updated_at: '2026-08-26T22:52:37.095670Z'
work_branch: OOMPAH-1346
target_branch: main
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
oompah.lifecycle_revision: 3
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  post_landed_parent_id: OOMPAH-1342
  task_branch: OOMPAH-1346
  base_branch: main
  base_sha: d258fc16b1478ff902139c66cdb3e51fa96d209c
  head_sha: 80b93f5d251e2b7d442dd85c2ac3ce91a99491bb
  submitted_at: '2026-08-26T20:32:49.473205+00:00'
  updated_at: '2026-08-26T20:32:49.473205+00:00'
oompah.work_branch: OOMPAH-1346
oompah.target_branch: main
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
author: oompah
created: 2026-08-26 19:32
---
Direct implementation is committed and pushed. Keep this task reserved for the current manual recovery session; do not dispatch it to the oompah worker.
---
author: oompah
created: 2026-08-26 20:27
---
Validation update: combined focused suites pass (756 tests). Full make test reached 20,447 passed with only tests/test_restart_api.py::test_repeated_replacement_timeout_detection_under_load timing out under parallel load; rerunning that test alone passes. No product failure observed.
---
author: oompah
created: 2026-08-26 20:31
---
Added bounded age-based retention for cold workflow events and removed scheduler-path VACUUM; focused storage/config tests pass.
---
author: oompah
created: 2026-08-26 20:32
---
Added bounded age-based retention for cold workflow events, removed scheduler-path VACUUM, and included the validated snapshot API prerequisite stack.
---
author: oompah
created: 2026-08-26 21:36
---
Implementation is committed, pushed, and present on the published epic branch. The complete make test gate passes functionally except for the known parallel-only 5-second restart stress timeout; that exact test passes in isolation. Awaiting integration while the project remains paused.
---
author: oompah
created: 2026-08-26 22:50
---
Full repository test gate completed successfully: 20,449 passed, 7 skipped, 2 xfailed. Changes are pushed and included in epic PR #951.
---
<!-- COMMENTS:END -->
