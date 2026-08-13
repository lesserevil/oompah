---
id: OOMPAH-1248
type: task
status: Open
priority: null
title: Retire durable implementation lease when its exact worker is gone
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T15:31:19.680451Z'
updated_at: '2026-08-13T15:31:25.608232Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: f0218931-be6f-4cb5-95a6-07fed101a5ec
  request_fingerprint: b8c144c366a6c34f419914e1ef22c69b9883f976f51482a4780e034c793f6a83
oompah.lifecycle_revision: 1
---
## Summary

Bug: an implementation_start job can complete with an ACTIVE durable disposition and a one-hour lease, then the provider worker exits immediately with no matching live RunningEntry. _refresh_durable_implementation_authority leaves the future lease unchanged when no live entry exists, so WorkDecision incorrectly reports implementation.active and schedules no recovery until lease expiry. Observed TRICKLE-141: start job 16866 completed, no owner claim/live agent, worker exited at zero turns, but decision remained owned until 15:52 UTC. Scope: make durable implementation authority require exact live-worker proof after the start/transition job is no longer pending; clear/expire the lease when an agent-sourced ACTIVE/HANDED_OFF disposition has no matching live entry, while preserving direct-owner and transition-in-flight authority. Add race/restart tests. Acceptance: dead workers promptly produce implementation_recovery, live exact workers remain owned, pending start transitions are not double-dispatched, and focused durable workflow tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

