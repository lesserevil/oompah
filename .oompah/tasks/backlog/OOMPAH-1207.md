---
id: OOMPAH-1207
type: bug
status: Backlog
priority: 1
title: Restart reconstruction recognizes protected imperative implementation jobs
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T02:28:41.440593Z'
updated_at: '2026-08-13T02:42:49.816970Z'
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
  creation_marker: restart-protected-imperative-deadlock-v1
  request_fingerprint: 797202381757f69a5b53e55ce41290011c271fb8242330dce8c5fd860a7a71c8
---
## Summary

Fix a scheduler deadlock in the durable workflow restart boundary. When ImplementationWorkflowController.reconcile_evaluated() encounters an active event:implementation:imperative job whose action differs from the current fact-derived action, WorkflowJobStore.materialize_event() intentionally preserves that protected job and returns an accepted write without a replacement fact job. The reconciliation report nevertheless counts the fact job as required but not materialized. Universal liveness then remains scan_complete=false/restart_reconstruction_pending=true, and worker admission is permanently deferred even though the imperative retry jobs are already queued. Scope: oompah/implementation_workflow.py and, if needed, the WorkflowEventWrite/proof API in oompah/workflow_jobs.py; preserve generation and protected-lane fencing. Add regression tests in tests/test_implementation_workflow.py and/or tests/test_workflow_runtime.py reproducing restart convergence with a different active imperative action. Acceptance: the active protected imperative job is treated as exact execution authority for reconciliation accounting, restart reconstruction converges, continue_admission_async can drain the job, stale/older fact scans still cannot replace it, and focused workflow tests plus the project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 02:42
---
Implemented the restart reconstruction fix on branch OOMPAH-1207. Protected imperative implementation jobs now satisfy the current fact decision's materialization obligation, both in implementation reconciliation accounting and universal restart proof. Regression coverage exercises fact reconciliation and two-cut restart liveness. Verification: 324 affected workflow suites passed; terminal-audit mutation scan passed; secret scan passed.
---
<!-- COMMENTS:END -->
