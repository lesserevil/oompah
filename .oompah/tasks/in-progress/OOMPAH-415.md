---
id: OOMPAH-415
type: task
status: In Progress
priority: null
title: Decouple stale-dispatch threshold from full_sync_interval and reduce recovery
  latency
parent: OOMPAH-414
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T19:34:14.691327Z'
updated_at: '2026-07-23T19:48:40.280243Z'
work_branch: epic-OOMPAH-414
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 9977cbe1-45e8-4d86-94b2-5eb8f654c2d2
oompah.work_branch: epic-OOMPAH-414
oompah.task_costs:
  total_input_tokens: 21
  total_output_tokens: 4763
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 21
      output_tokens: 4763
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 21
    output_tokens: 4763
    cost_usd: 0.0
    recorded_at: '2026-07-23T19:48:26.010330+00:00'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 19:46
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 19:46
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 19:48
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-415 is a unique, first-of-its-kind task.

**Investigation scope:**
- Searched all .oompah/tasks/ states (open, backlog, done, archived, merged) — 280+ tasks total
- Grep patterns: dispatch_stale, dispatch_loop_stale, stale_factor, dispatch_stale_threshold, stale_dispatch, recovery_latency, full_sync_interval, heartbeat, decouple, grace_period
- Searched docs/ and plans/ directories including docs/tick-latency-diagnostics.md
- Verified current code in oompah/config.py and oompah/orchestrator.py

**Findings:**
- No existing task covers decoupling dispatch_stale_threshold from full_sync_interval
- No existing task adds dispatch_stale_threshold_ms or dispatch_stale_grace_ms config fields
- The code in oompah/config.py currently only has dispatch_loop_stale_factor (factor-based formula: full_sync_interval_ms × 3.0 = 15 min threshold)
- The code in oompah/orchestrator.py uses this factor-based formula in is_dispatch_loop_stale(), check_and_recover_dispatch_loop(), and _arm_dispatch_stale_alert()
- dispatch_stale_threshold_ms and dispatch_stale_grace_ms do NOT yet exist anywhere in the codebase
- tests/test_dispatch_loop_heartbeat.py exists and needs extension per the task spec

**Key files for implementation:**
- oompah/config.py (lines ~563, ~947-949) — add dispatch_stale_threshold_ms and dispatch_stale_grace_ms fields
- oompah/orchestrator.py (lines ~2426-2593) — update is_dispatch_loop_stale(), check_and_recover_dispatch_loop(), _arm_dispatch_stale_alert()
- docs/tick-latency-diagnostics.md — add new vars to config table, update 15-min references
- .env.example — add commented-out OOMPAH_DISPATCH_STALE_THRESHOLD_MS=120000 and OOMPAH_DISPATCH_STALE_GRACE_MS=30000
- tests/test_dispatch_loop_heartbeat.py — add 4 new test cases

**Remaining work:** Full implementation as described in the task description.

**Recommended next focus:** feature
---
author: oompah
created: 2026-07-23 19:48
---
Agent completed successfully in 137s (4784 tokens)
---
author: oompah
created: 2026-07-23 19:48
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 43, Tool calls: 30
- Tokens: 21 in / 4.8K out [4.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 17s
- Log: OOMPAH-415__20260723T194613Z.jsonl
---
author: oompah
created: 2026-07-23 19:48
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 19:48
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 19:48
---
Focus: Technical Writer
---
<!-- COMMENTS:END -->
