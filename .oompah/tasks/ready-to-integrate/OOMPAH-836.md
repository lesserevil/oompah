---
id: OOMPAH-836
type: task
status: Ready to Integrate
priority: 1
title: Bind integration delivery and recovery to exact durable handlers
parent: OOMPAH-804
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:38.407330Z'
updated_at: '2026-08-06T09:39:30.682287Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-836
  head_sha: f89c477d4c03a8992a7278337182c0352da5de16
  submitted_at: '2026-08-06T09:39:23.200622+00:00'
  updated_at: '2026-08-06T09:39:23.200622+00:00'
---
## Summary

Implement production task-scoped handlers for all seven IntegrationWorkflow actions: landing refresh, terminal stage, historical audit replay, integration attempt, integration recovery, standalone delivery, and epic-branch reconciliation. Split the one-item integration executor and queue completion/coordination/audit staging from _process_integration_queues; make the workflow job lease the enforce-mode authority rather than a competing IntegrationQueue lease. Extract one-candidate standalone forge delivery and exact branch/rebase repair without invoking project-wide sweeps. Extend action-specific observations/results so maintenance actions do not unconditionally call integrate(). Relevant files: oompah/integration_workflow.py, oompah/workflow_runtime.py or typed adapters, integration executor/queue, orchestrator delivery/replay/standalone/branch repair paths. Required tests: immutable private heads, changed parent ancestry, executor crash and restart, retry/recovery, same-head replay, historical terminal staging, standalone review creation/adoption, multi-project routing, effect receipts, and enforce single-writer assertions. Acceptance: each action has an exact project/task handler and verification receipt; restart resumes rather than duplicates; no global sweep or second queue owner escapes the job boundary.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 09:39
---
Integration delivery/recovery handlers and regression coverage are complete, with exact commit 867be73e included in canonical validated composition f89c477d. Resubmitting canonical head after OOMPAH-858 task-scoped nested-delivery recovery so gate, integration, and audit share one exact candidate.
---
<!-- COMMENTS:END -->
