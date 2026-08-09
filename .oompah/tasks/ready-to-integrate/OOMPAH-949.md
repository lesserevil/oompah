---
id: OOMPAH-949
type: bug
status: Ready to Integrate
priority: 1
title: Make fresh-waiter priority regression independent of host scheduling
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T10:18:16.575025Z'
updated_at: '2026-08-09T10:28:38.023157Z'
work_branch: OOMPAH-949
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-949
  head_sha: 27c3685dc3d2e4aba8e852a88569795acd300fe7
  submitted_at: '2026-08-09T10:28:20.807004+00:00'
  updated_at: '2026-08-09T10:28:20.807004+00:00'
oompah.work_branch: OOMPAH-949
---
## Summary

Triggered by: OOMPAH-946

Full make test for OOMPAH-946 on 2026-08-09 reached 18,890 passing tests but intermittently failed tests/test_validation_resource_lease.py::test_cancelled_aged_waiter_does_not_transfer_protection: the fresh worker acquired before the fresh exact waiter. The test configures aging_seconds=0.01, so normal host scheduling can age the nominally fresh worker before the exact waiter is durably queued; 634-module coverage and 20 immediate isolated reruns passed. Determine whether the observed ordering is solely the real-clock fixture assumption or exposes a lease selection race. Make the regression deterministic with a controlled clock and explicit freshness boundary if production is correct, or repair the selection fence if exact work can lose while both waiters are provably fresh. Preserve bounded aging and no-starvation from OOMPAH-905, exact urgency for genuinely fresh waiters, FIFO within effective priority, cancellation cleanup, restart persistence, and capacity safety. Required tests: a cancelled aged waiter cannot transfer age; a fresh exact waiter overtakes a provably fresh worker; a genuinely aged worker still receives its fairness boost; repeated focused runs under artificial scheduling delay; complete make test. Acceptance: ordering assertions derive from explicit durable timestamps rather than sub-10ms scheduler timing and the full gate is stable under load.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 10:28
---
Investigation proved the full-gate ordering was correct production behavior: with aging_seconds=0.01, the observed ~210 ms xdist scheduling pause moved the worker across all 21 aging bands, so its starvation protection legitimately outranked the later exact waiter. Commit 27c3685dc keeps replacement waiters in an explicit 30-second aging band (630-second starvation window), artificially reproduces the 250 ms hosted pause, and asserts durable telemetry for the genuinely aged cancelled waiter and both fresh replacements before release. Production selection code is unchanged. Verification: the regression passed 10 consecutive runs; all 499 validation-resource lease tests passed; five focused priority/cancellation/restart/multiprocess tests, Ruff, terminal mutation scan, and secret scan passed. The preceding OOMPAH-946 full gate had already passed the other 18,890 tests before exposing this one test assumption.
---
author: oompah
created: 2026-08-09 10:28
---
Made the cancelled-waiter aging regression independent of host scheduling by using explicit durable freshness/starvation windows, reproducing the hosted scheduling gap, and asserting effective-priority evidence before capacity release. Production fairness behavior remains unchanged. Commit 27c3685dc is pushed; 499 lease tests and 10 repeated reproductions pass.
---
<!-- COMMENTS:END -->
