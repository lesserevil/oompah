---
id: OOMPAH-1210
type: bug
status: Backlog
priority: 1
title: Retire exhausted fact authority when imperative recovery takes over
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T03:23:09.049536Z'
updated_at: '2026-08-13T03:23:09.049536Z'
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
  creation_marker: implementation-cross-lane-exhaustion-retirement-v1
  request_fingerprint: 4d7141f1c88a1aeda0fb22cd95b74276f1ebabc5d622fc0c9f0286cb4e779208
---
## Summary

Fix cross-lane exhaustion authority in the implementation workflow. An active event:implementation:imperative retry can supersede an exhausted event:implementation:fact generation under the shared implementation ordering namespace, but current_exhausted_jobs still treats the older fact row as authoritative because retirement only recognizes same-lane successors. The universal projection then reports retry.exhausted and blocks restart worker admission even though an exact queued imperative retry owns recovery (observed live on TRICKLE-118). Scope: record a durable event-handoff retirement when materialize_event atomically enqueues a successor that explicitly supersedes sibling lanes, and teach current-exhaustion proof to honor only that exact replacement authority; avoid retiring unrelated lanes. Relevant files: oompah/workflow_jobs.py, oompah/implementation_workflow.py if needed, and focused workflow store/controller/runtime tests. Acceptance: a queued imperative retry retires prior fact-lane exhaustion; if the retry itself exhausts it remains actionable; unrelated/different lanes cannot suppress exhaustion; restart liveness no longer projects stale retry.exhausted; focused tests and the project gate pass. After deployment, rearm or replay the exact live TRICKLE-118 retry through supported workflow authority so the in-flight task resumes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

