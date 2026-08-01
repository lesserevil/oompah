---
id: OOMPAH-676
type: task
status: Open
priority: null
title: Make graceful CLI cutover drain workers before restart
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T05:18:04.532392Z'
updated_at: '2026-08-01T05:18:08.287670Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Bug discovered while clearing the post-deploy auth-health alert on 2026-08-01. The documented make restart/make graceful path promises to drain active agents, but scripts/canonical_cli_cutover.py first POSTs /api/v1/orchestrator/pause. Orchestrator.pause() immediately schedules _terminate_all_running(), so _wait_for_state(paused and running==0) observes terminated workers rather than naturally completed workers. In the live reproduction, OOMPAH-675 run #1 exited terminated during make graceful and had to be redispatched after restart. Implementation scope: introduce or use a pause-dispatch-only/quiesce operation for canonical cutover, preserve existing explicit pause semantics, let running workers finish until the configured drain timeout, persist and terminate/recover only truly undrained workers at timeout, and keep CLI/server transactional cutover guarantees. Relevant files: scripts/canonical_cli_cutover.py, oompah/server.py, oompah/orchestrator.py, tests/test_lifecycle_cli_sync_integration.py, tests/test_makefile_restart_wait.py, and restart lifecycle tests. Acceptance criteria: make restart/make graceful stop new dispatch without terminating active workers before timeout; a worker that completes during drain is not redispatched; a timed-out worker is safely recovered exactly once; explicit operator pause behavior remains compatible; focused lifecycle and integration tests cover the live regression.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

