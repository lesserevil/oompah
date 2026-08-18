---
id: OOMPAH-1268
type: task
status: Backlog
priority: null
title: Archive workflow_job_events for Archived tasks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-18T16:49:48.891025Z'
updated_at: '2026-08-18T16:51:41.560843Z'
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
  creation_marker: 3211e93d-73f6-4a41-99a7-1bdcaa479ed0
  request_fingerprint: 2efda9a8ba2e984ce57f567673ef41d1f8d9cc0aaaf21d0aff8871d9296ce4a0
---
## Summary

The durable workflow_jobs.sqlite3 grew to ~5GB because workflow_job_events is append-only and never pruned (19.8M rows). Add a bounded maintenance job that relocates job events for tasks with a durable lifecycle-final:Archived retirement proof into a new workflow_job_events_archive cold table, preserving original sequences and a persisted high-water mark so the snapshot-authority ABA fence (capture_snapshot_authority) never regresses.

Scope/files:
- oompah/workflow_jobs.py: schema V8 (archive table + guard row + task index), high-water meta key advanced in _append_event_locked, capture_snapshot_authority reads max(live, high-water), new archive_lifecycle_final_events(max_tasks,max_events).
- oompah/orchestrator.py: schedule _archive_workflow_events in _run_non_lifecycle_housekeeping (min_interval 300s).
- tests: tests/test_workflow_jobs.py (move/high-water/budget/skip/guard), tests/test_workflow_retirement_architecture.py (housekeeping bundle).

Acceptance: append-only DELETE still blocked outside archival; archived events moved to cold table with sequences preserved; snapshot authority high-water preserved after archival; maintenance job runs bounded and restart-safe; full suite green.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-18 16:51
---
Implemented in PR #883 (branch workflow-event-archival), auto-merge enabled pending CI. Schema V8 archive table + high-water fence; bounded maintenance job in non-lifecycle housekeeping (300s). Local suites green (test_workflow_jobs, test_workflow_retirement_architecture, test_orchestrator_handlers, test_storage_cleanup = 543 passed). Will restart service onto merged revision after CI merges.
---
<!-- COMMENTS:END -->
