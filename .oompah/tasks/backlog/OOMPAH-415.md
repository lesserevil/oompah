---
id: OOMPAH-415
type: task
status: Backlog
priority: null
title: Decouple stale-dispatch threshold from full_sync_interval and reduce recovery
  latency
parent: OOMPAH-414
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T19:34:14.691327Z'
updated_at: '2026-07-23T19:34:14.691327Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

### Problem

The stale-dispatch recovery window is currently full_sync_interval_ms × dispatch_loop_stale_factor (300s × 3.0 = 15 min) plus a grace period of 1 × full_sync_interval_ms (300s = 5 min) before recovery fires — up to 20 minutes total. This is too long; newly eligible work can wait 15+ minutes with no dispatch.

### Scope

In oompah/config.py:
- Add a new field dispatch_stale_threshold_ms (default: 120000, i.e. 2 minutes). Configurable via OOMPAH_DISPATCH_STALE_THRESHOLD_MS env var.
- Keep dispatch_loop_stale_factor as a backward-compat path: if dispatch_stale_threshold_ms is explicitly set to 0, fall back to the old factor-based formula. Otherwise, use the new field directly.
- Also add dispatch_stale_grace_ms (default: 30000, i.e. 30 seconds) to control the grace period before recovery fires. Configurable via OOMPAH_DISPATCH_STALE_GRACE_MS.

In oompah/orchestrator.py:
- Update is_dispatch_loop_stale() to use config.dispatch_stale_threshold_ms instead of full_sync_interval_ms × dispatch_loop_stale_factor.
- Update check_and_recover_dispatch_loop() to use config.dispatch_stale_grace_ms for the grace period instead of full_sync_interval_ms.
- Update the alert message in _arm_dispatch_stale_alert() to show the new threshold.
- Update _full_sync_due() docstring comments if they reference the old stale formula.

In docs/tick-latency-diagnostics.md:
- Add OOMPAH_DISPATCH_STALE_THRESHOLD_MS and OOMPAH_DISPATCH_STALE_GRACE_MS to the Key Configuration Variables table.
- Update the 15-minute threshold references to reflect the new 2-minute default.

In .env.example:
- Add commented-out OOMPAH_DISPATCH_STALE_THRESHOLD_MS=120000 and OOMPAH_DISPATCH_STALE_GRACE_MS=30000 with explanatory comments.

### Tests

Extend tests/test_dispatch_loop_heartbeat.py:
- Test that is_dispatch_loop_stale() uses dispatch_stale_threshold_ms when set.
- Test that check_and_recover_dispatch_loop() uses dispatch_stale_grace_ms for grace.
- Test that recovery fires before the old 15-minute threshold.
- Test backward compat: dispatch_stale_threshold_ms=0 falls back to factor-based formula.

Run make test before committing.

### Acceptance

A stall is detected and recovery triggered within 2 minutes (default) instead of the previous 15-20 minutes. The threshold is independently tunable without touching full_sync_interval_ms.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

