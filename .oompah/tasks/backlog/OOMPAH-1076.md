---
id: OOMPAH-1076
type: task
status: Backlog
priority: null
title: Bound large-corpus workflow reconciliation within restart SLO
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T09:41:07.342509Z'
updated_at: '2026-08-11T09:41:07.342509Z'
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
  creation_marker: 0bd548a4-8b7b-45c6-b787-41efab3e0d67
  request_fingerprint: 5ea2f35f9115133371ebbc0341e287e822a967ee1c6968758bc9be0582b7a261
---
## Summary

Live regression observed 2026-08-11 after the OOMPAH-1075 cache-generation correction was prepared: a full WorkflowRuntime reconciliation over 1,878 tasks consumes roughly 138-215 seconds of one executor CPU core before publication. The server event loop remains responsive and publication locks show zero wait, but restart reconstruction has a 120-second deadline; the monolithic cut therefore becomes restart_overdue even without lock contention, and any legitimate authority change can discard minutes of work. This is distinct from OOMPAH-969 prompt effect admission, OOMPAH-986 terminal-audit scoped publication, and OOMPAH-1075 false read-cache generation churn. Implementation scope: instrument and bound full-corpus collection, then optimize, chunk, or retain/retry stable project/task work so a restart can publish a complete authoritative snapshot within 120 seconds under ordinary concurrent tracker activity. Preserve fail-closed same-task/project authority, atomic durable snapshot/effect publication, pause/quiesce behavior, worker admission fencing, and terminal-audit/review exactness. Relevant code: oompah/workflow_runtime.py and its domain collectors/native tracker access paths. Required tests: deterministic large-corpus restart with a concurrent three-minute branch gate and ordinary tracker mutation; prove a fresh complete snapshot publishes and restart_pending clears within 120 seconds while admission remains fail-closed until it does; prove affected authority is recomputed without duplicating effects; prove event-loop/control endpoints remain responsive; include performance/phase telemetry that identifies regressions. Acceptance: the live-equivalent 1,878-task canary publishes a complete current snapshot inside the configured 120-second restart SLO, repeated ordinary mutations cannot indefinitely starve it, focused workflow/native-tracker tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

