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
updated_at: '2026-08-01T05:18:23.601787Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f2deedf4e59e17e8fe42b8b61a88e8c80a14dd478df80f936e3993911b4c31eb
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 417f065c-acc8-4729-8677-806088db2c48
  claim_owner: 8c3ebf5f-5e74-47c3-8b48-e3150c200cf1
  claimed_at: '2026-08-01T05:18:18.362231+00:00'
  claim_expires_at: '2026-08-01T05:48:18.362231+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 0bc0cd65-b15b-44f0-8b34-d22b476697c1
---
## Summary

Bug discovered while clearing the post-deploy auth-health alert on 2026-08-01. The documented make restart/make graceful path promises to drain active agents, but scripts/canonical_cli_cutover.py first POSTs /api/v1/orchestrator/pause. Orchestrator.pause() immediately schedules _terminate_all_running(), so _wait_for_state(paused and running==0) observes terminated workers rather than naturally completed workers. In the live reproduction, OOMPAH-675 run #1 exited terminated during make graceful and had to be redispatched after restart. Implementation scope: introduce or use a pause-dispatch-only/quiesce operation for canonical cutover, preserve existing explicit pause semantics, let running workers finish until the configured drain timeout, persist and terminate/recover only truly undrained workers at timeout, and keep CLI/server transactional cutover guarantees. Relevant files: scripts/canonical_cli_cutover.py, oompah/server.py, oompah/orchestrator.py, tests/test_lifecycle_cli_sync_integration.py, tests/test_makefile_restart_wait.py, and restart lifecycle tests. Acceptance criteria: make restart/make graceful stop new dispatch without terminating active workers before timeout; a worker that completes during drain is not redispatched; a timed-out worker is safely recovered exactly once; explicit operator pause behavior remains compatible; focused lifecycle and integration tests cover the live regression.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 05:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 05:18
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
