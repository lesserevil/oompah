---
id: OOMPAH-715
type: task
status: Open
priority: null
title: Make full-sync event-loop test deterministic under full-gate load
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T01:08:30.439967Z'
updated_at: '2026-08-03T01:09:44.191463Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6bd19602e6ff713923c7e4430956c6722b2579dc3876e25497aa6e6413b85557
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 1a2a8eb5-8d63-45ec-871b-eab6183d00d8
  claim_owner: ac52e8ec-836b-4534-92a2-d2acfef0120b
  claimed_at: '2026-08-03T01:09:36.235700+00:00'
  claim_expires_at: '2026-08-03T01:39:36.235700+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d0427dce-b528-488a-beae-6dade84db42e
---
## Summary

Triggered by the OOMPAH-711 exact-head branch gate on 2026-08-03. The full parallel make test run failed tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_full_sync_loop_posts_full_sync_events while nine other deterministic fixture failures were present. The exact event-loop test passed immediately afterward and passed ten consecutive isolated retries, identifying a load/timing-dependent test race rather than a stable OOMPAH-711 behavior regression.

Implementation scope:
- Reproduce the full-sync event posting failure under parallel or delayed scheduling and identify the implicit wall-clock, background-loop, or teardown assumption.
- Replace sleeps or timing windows with explicit synchronization around the full-sync event emission and consumption being asserted.
- Ensure every loop task, event waiter, executor, and mocked clock is deterministically quiesced at test teardown.
- Preserve production event-driven-loop timing and safety-net full-sync semantics.

Relevant code: tests/test_event_driven_loop.py TestRunEventDrivenLoop, oompah/orchestrator.py event-driven loop and full-sync scheduling, and shared asyncio fixtures. Gate evidence is recorded in OOMPAH-711 comment 15.

Required tests:
- Force delayed event-loop scheduling and prove the assertion waits for the exact full-sync event rather than elapsed wall time.
- Repeated parallel execution cannot reproduce the failure.
- Cancellation and shutdown leave no pending task or closed-loop subprocess/resource warning.
- Existing event-driven invalidation and safety-net tests remain green.

Acceptance criteria:
- Replaying the OOMPAH-711 full-gate load cannot fail this test from scheduling order.
- The test uses an explicit deterministic barrier and leaves no live background work.
- Production loop behavior is unchanged.
- Focused event-driven-loop tests and make test/check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 01:08
---
Project owner promoted this race follow-up to Open. The exact test passed ten consecutive isolated retries after the OOMPAH-711 full-gate failure; implementation should reproduce delayed parallel scheduling and replace the implicit timing window with an explicit barrier.
---
author: oompah
created: 2026-08-03 01:09
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 01:09
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
