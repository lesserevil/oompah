---
id: OOMPAH-349
type: bug
status: Archived
priority: 1
title: Make project tracker refresh timeouts real
parent: OOMPAH-348
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T00:56:34.088413Z'
updated_at: '2026-08-02T01:46:00.003706Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-489c8eaf701c: '2026-08-02T01:45:54.603478+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-349
    target_state: Archived
    evidence_fingerprint: b8a3cfe80c291913878c1d8a16754806ed4de2e65f551d1f29dbcbc6e5b9c45d
    audit_ids:
    - audit-b0ef813cb617
    kind: result
    applied: true
    retired_at: '2026-08-02T01:45:54.603492+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-349
    audit_id: audit-b0ef813cb617
    attempt_id: attempt-489c8eaf701c
    target_state: Archived
    evidence_fingerprint: b8a3cfe80c291913878c1d8a16754806ed4de2e65f551d1f29dbcbc6e5b9c45d
    status: Archived
    audit_ids:
    - audit-b0ef813cb617
    applied: true
    created_at: '2026-08-02T01:45:54.603511+00:00'
    applied_at: '2026-08-02T01:45:59.064289+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b0ef813cb617
    project_id: proj-14849f1b
    task_id: OOMPAH-349
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b8a3cfe80c291913878c1d8a16754806ed4de2e65f551d1f29dbcbc6e5b9c45d
    attempts:
    - version: 1
      attempt_id: attempt-489c8eaf701c
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: b8a3cfe80c291913878c1d8a16754806ed4de2e65f551d1f29dbcbc6e5b9c45d
      created_at: '2026-08-02T01:27:35.036401+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:27:35.036401+00:00'
      branch_key: OOMPAH-349
      verdict: pass
      completed_at: '2026-08-02T01:45:54.603249+00:00'
      ended_at: '2026-08-02T01:45:54.603249+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:23.849923+00:00'
    updated_at: '2026-08-02T01:45:54.603249+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-489c8eaf701c
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b8a3cfe80c291913878c1d8a16754806ed4de2e65f551d1f29dbcbc6e5b9c45d
    created_at: '2026-08-02T01:27:35.036401+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:27:35.036401+00:00'
    branch_key: OOMPAH-349
---
## Summary

Problem: candidate and in-progress project refreshes call synchronous tracker methods inside an inner asyncio event loop. asyncio.wait_for cannot interrupt that blocking call, so the configured refresh timeout is ineffective; production candidate fetch blocked for 218 seconds.

Implement: execute each blocking tracker read in a worker executor, then apply asyncio timeout to the awaited future. Preserve per-project concurrency limits and stale-cache fallback. Cancellation/timeout must not leave unbounded queued work or leak executor tasks. Ensure candidate and in-progress refreshes share the safe helper.

Tests: simulate a blocking tracker read; assert the operation returns stale/empty data within configured timeout, records timeout metrics, and other projects still complete. Regression test that the old inner-loop blocking pattern cannot exceed the configured timeout.

Acceptance: a single hung tracker operation cannot stall the scheduler beyond project_refresh_timeout_ms plus small scheduling overhead; healthy projects remain dispatchable; make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:07
---
Implemented bounded candidate refreshes: blocking tracker reads enter the executor before the per-project deadline, stale data is used on timeout, and an in-flight hung read is reused rather than stacking workers. Regression coverage added; full suite is running.
---
author: oompah
created: 2026-07-22 01:15
---
Implemented bounded, isolated candidate and in-progress refreshes with stale-cache fallback and regression tests.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: bounded tracker refresh deadlines and stale-cache fallback is present on origin/main in commit 6dd2cdfcf. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 6dd2cdfcf and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:27
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-02 01:27
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-02 01:45
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- delivery_commit: 6dd2cdfcf Harden scheduler against blocking tracker work
- commit_on_main: true
- orchestrator_helper: oompah/orchestrator.py:1594 _run_bounded_refresh with asyncio.wait_for + stale cache fallback
- candidate_refresh_path: oompah/orchestrator.py ~8816 run_in_executor(self._refresh_pool, _read) with asyncio.shield of in-flight future
- in_progress_refresh_path: oompah/orchestrator.py ~8927 mirrors candidate path via _run_bounded_refresh('in_progress', ...)
- config_knob: oompah/config.py:637 project_refresh_timeout_ms default 10000
- regression_tests: tests/test_long_tick_regression.py: test_bounded_refresh_timeout_unblocks_other_projects, test_slow_project_tracker_timeout_does_not_block_other_project_dispatch, test_snapshot_project_refresh_shows_timeout_count
- focused_test_results: test_long_tick_regression.py 14 passed; test_orchestrator_handlers.py 277 passed; test_dispatch_loop_heartbeat.py + test_task_cost_telemetry.py 90 passed
- previous_state: Merged
- archive_reason: Aged Merged auto-archive (closed 7 days ago)
---
<!-- COMMENTS:END -->
