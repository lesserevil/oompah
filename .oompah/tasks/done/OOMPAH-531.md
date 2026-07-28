---
id: OOMPAH-531
type: task
status: Done
priority: 2
title: Schedule duplicate preflight from spare agent capacity
parent: OOMPAH-528
children: []
blocked_by:
- OOMPAH-530
labels: []
assignee: null
created_at: '2026-07-28T21:19:12.151334Z'
updated_at: '2026-07-28T21:43:09.204536Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Integrate duplicate preflight into each orchestrator scheduling tick after the evidence and claim APIs from OOMPAH-529 and OOMPAH-530 exist.

Implementation scope:
- During every scheduling tick, collect Open tasks that are non-terminal, otherwise dispatchable, not dependency-blocked, not already claimed, and unchecked or stale for the configured duplicate detector version.
- Preserve the existing inexpensive _apply_duplicate_detection pass. A heuristic match may still immediately produce Duplicate Candidate, but a heuristic miss must not be written as a model-backed pass.
- Allocate only otherwise-available configured agent capacity to preflight and enforce a configurable cap. Add OOMPAH_DUPLICATE_PREFLIGHT_MAX_AGENTS to .env.example and ServiceConfig; default to 1. A value of 0 disables model-backed background preflight.
- Preserve an implementation lane: when checked implementation-ready work is waiting, preflight must not consume the final available slot. If no checked work is waiting, preflight may use available slots up to its cap.
- Use the normal provider/focus selection for duplicate_detector, but attach the separate preflight claim and do not transition the issue to In Progress.
- Define deterministic ordering using existing task priority/age ordering so repeated ticks do not starve older Open work.
- Respect project pause, global pause, provider availability/whitelists, budgets, one-agent-per-epic/shared-branch constraints where applicable, and max-concurrency auto-scaling.
- Re-evaluate capacity and eligible tasks on every scheduling tick. Never kill a running preflight when capacity later shrinks.
- Add counters/log reasons for selected, started, skipped-no-capacity, skipped-reserved-slot, stale, already-checked, and claim-race-lost.

Relevant context/files:
- oompah/orchestrator.py: _handle_dispatch_needed_locked, _apply_duplicate_detection, _select_dispatchable, _available_slots, focus dispatch.
- oompah/config.py and .env.example for configuration.
- oompah/focus.py for duplicate_detector selection.
- tests/test_orchestrator_duplicate_detection.py and scheduler/capacity tests for existing patterns.

Required tests:
- An unchecked Open task starts preflight when a slot is spare and remains Open.
- A checked implementation-ready task receives the reserved last slot before additional preflight.
- Multiple slots respect the preflight cap; cap 0 disables preflight.
- Paused, blocked, terminal, active, or already-checked tasks are skipped with the correct reason.
- Auto-scaled concurrency is re-evaluated each tick and reductions do not terminate existing runs.
- Ordering is deterministic and old unchecked tasks are not starved.

Acceptance criteria:
1. Open tasks can be screened before implementation without a user-visible In Progress transition.
2. Background screening cannot monopolize all useful implementation capacity.
3. All existing dispatch constraints continue to apply and claim races are harmless.
4. Configuration is loaded only through OOMPAH_* environment settings and documented in .env.example.
5. Focused scheduler and capacity tests pass through the appropriate Makefile target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 21:42
---
Claimed by the current interactive Codex session before OOMPAH-530 completion. Core scheduler work is pushed on epic-OOMPAH-528; do not dispatch another agent.
---
author: oompah
created: 2026-07-28 21:43
---
Implemented and pushed in 7a2e467fb: per-tick spare-capacity selection, implementation-first ordering, configurable cap, forced duplicate-detector focus, pause/budget/dependency/shared-epic gates, deterministic ordering, and metrics. Scheduler regressions pass.
---
<!-- COMMENTS:END -->
