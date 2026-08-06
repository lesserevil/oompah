---
id: OOMPAH-845
type: task
status: Open
priority: null
title: Stabilize restart-recovery state fencing test under saturated full gates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T03:38:29.127146Z'
updated_at: '2026-08-06T03:44:23.429590Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Regression after OOMPAH-805: OOMPAH-791 exact head c402ffe9b reached 16,193 passing tests, then tests/test_event_driven_loop.py::TestGracefulRestartShutdownEvent::test_restart_recovery_preserves_superseding_state[In Validation] failed near the end of the xdist gate. The exact parameter passes alone and passed 20/20 four-way concurrent focused reproductions at about 1.2 seconds, indicating saturated full-suite scheduling/storage/thread-pool latency against the global five-second test timeout rather than a deterministic state-fencing failure. Implementation scope: inspect Orchestrator construction, state save/load, asyncio.to_thread tracker read, and event-loop fixture cleanup for unrelated work; isolate any unrelated corpus/background work and give the bounded restart-recovery lifecycle assertion an explicit timeout only if its production-relevant async/thread transition legitimately needs loaded-gate headroom. Do not weaken production restart fencing or raise the global timeout. Relevant files: tests/test_event_driven_loop.py and production restart recovery only if a real leak/unbounded path is found. Required tests: all four superseding-state parameters, at least 20 repeated four-way focused runs, complete event-driven-loop module serial and -n 4, event-loop/thread cleanup assertions, and make test. Acceptance: the exact test remains semantically strict, never rewrites Merged/Archived/In Validation/Needs Human, clears the durable restart record once, leaves no live loop/thread work, and passes saturated exact gates deterministically.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 03:44
---
Additional focused evidence: after the minimal marker, the complete event-driven-loop module passed 60/60 with -n 4, but pytest emitted a destroyed-pending quarantine-worker task from another test in the same module. Include that event-loop cleanup leak in the systemic audit/acceptance rather than treating a warning from normal teardown as healthy. The in-flight OOMPAH-791 workaround remains scoped only to the proven restart-recovery timeout.
---
<!-- COMMENTS:END -->
