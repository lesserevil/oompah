---
id: OOMPAH-909
type: task
status: In Progress
priority: null
title: Close owned Orchestrator resources between tests and on shutdown
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T12:20:40.667997Z'
updated_at: '2026-08-08T12:56:13.137953Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Bug reproduced on composed systemic head b4c6827: the exact four-worker full gate accumulated roughly 800-1100 open SQLite/WAL/SHM and workflow authority-lock descriptors per worker, then multiple standalone delivery tests hit the 5-second timeout and xdist deadlocked without JUnit at 81-99%. All 111 prior semantic failures pass in isolation, proving order/load contamination. Implement deterministic per-test ownership cleanup for successfully constructed Orchestrator pools and the five persistent SQLite stores without cancelling unrelated event-loop tasks or widening the global timeout. Fix production _drain_background_work so coordination_store and integration_queue are closed through a serialized idempotent resource boundary despite concurrent stop/run-finally drains. Relevant files: tests/conftest.py or a shared test-resource helper, oompah/orchestrator.py, and focused resource/store tests. Required tests: reproduce repeated real Orchestrator construction without FD growth; prove cleanup is idempotent and compatible with existing explicit closes; prove tick/refresh/integration pools are drained before stores; prove production stop closes coordination/integration descriptors under repeated/concurrent drain; rerun affected standalone/watchdog/terminal clusters and the exact full four-worker gate. Acceptance: no per-test descriptor accumulation, no live owned executor threads cross test boundaries, production graceful shutdown releases every owned persistent store, and the global 5-second test timeout remains unchanged.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 12:21
---
Claimed directly for the systemic composition workaround. Exact reproduction: full b4c6827 gate timed out at 99% with 53 failures and no JUnit; verbose fail-fast reproduced three five-second timeouts in tests/test_standalone_ready_to_integrate.py at 81%, then xdist deadlocked. Workers held about 800 persistent SQLite/authority-lock descriptors each. Implementing the harness and production shutdown repair on the active OOMPAH-763 composition head.
---
author: oompah
created: 2026-08-08 12:56
---
Implemented resource ownership repair at composed head b80e632fcb55658d37aa267bc7fa71ef0f044991: centralized exact-object/idempotent shutdown covers pools, runtime journals, receipt ledger, coordination/integration/review/workflow/transition stores; shielded implementation mutations now drain; pytest constructor/cleanup boundary is race-safe; WorkflowJobStore failed-init FD ownership is idempotent. Focused validation is green and the exact full branch gate is running under the dedicated validation lease.
---
<!-- COMMENTS:END -->
