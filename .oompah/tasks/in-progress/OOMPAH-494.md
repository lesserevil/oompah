---
id: OOMPAH-494
type: task
status: In Progress
priority: 1
title: Consolidate Granian subprocess tests into complete scenarios
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels:
- focus-complete:duplicate_detector
- needs:test
assignee: null
created_at: '2026-07-28T13:53:29.472352Z'
updated_at: '2026-07-28T15:32:10.452385Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e394b507-8596-4301-851f-21abd01a88fc
oompah.work_branch: epic-OOMPAH-490
---
## Summary

Implementation scope

Refactor `tests/test_granian_e2e.py`, whose function-scoped server fixture currently starts a Granian subprocess for many single assertions. Preserve the externally meaningful coverage in four or five scenario tests: HTTP root/state contract; WebSocket connection plus complete initial state/issues push; two-client refresh/broadcast fan-out; and restart followed by HTTP and WebSocket verification. Combine assertions that consume the same response or socket session. Keep a separate multiple-client scenario only if it exercises behavior not already covered by fan-out. Centralize process ownership in a context manager or fixture that always executes bounded SIGINT/terminate/kill cleanup and drains pipes, including on assertion failure or KeyboardInterrupt. Do not weaken `tests/test_granian_parity.py` or unit-level WebSocket lifecycle tests.

Tests

Run the refactored file repeatedly, including once with `pytest -x`, and verify no child matching the generated Granian E2E script remains after completion. Record collected cases and runtime before and after. Run `make test` after the Git-remote safety task is complete.

Acceptance criteria

All documented Granian E2E contracts remain asserted, collected cases fall from 20 to no more than 6, repeated server startup is limited to one per independent scenario, cleanup leaves no subprocess, and the file's runtime decreases materially without adding timing-sensitive skips.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 15:29
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 15:29
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 15:30
---
Understanding: duplicate-screening only. I will search native task history and project documentation for Granian E2E/subprocess-test consolidation work, inspect plausible candidates in full, and either archive a confirmed duplicate or hand off with evidence for implementation.
---
author: oompah
created: 2026-07-28 15:31
---
Discovery: No confirmed duplicate. Repository-wide searches for Granian, test_granian_e2e, subprocess cleanup, WebSocket fan-out, restart, SIGINT, and pipe draining found no task with this consolidation scope. Closest full tasks reviewed: parent OOMPAH-490 uniquely assigns Granian scenario consolidation to OOMPAH-494; OOMPAH-499 covers unrelated exact clones/name shadowing; OOMPAH-500 is the downstream final runtime/process-leak audit; archived OOMPAH-172 fixes global orchestrator pollution affecting Granian parity, not E2E process ownership. Git history identifies legacy TASK-472 as the suite's origin: it added the 20 contracts with a module fixture, then commit 3c992af47 intentionally switched to one subprocess per test after WebSocket close/handshake hangs. That legacy tracker ID is no longer viewable (404), but its commit history shows creation/stabilization rather than the current scenario-level consolidation and bounded cleanup work.
---
author: oompah
created: 2026-07-28 15:32
---
Focus handoff: duplicate_detector

1. Outcome: No confirmed duplicate; OOMPAH-494 should proceed as its own Granian E2E test-refactor task.
2. Evidence: Searched .oompah/tasks, docs, plans, README.md, and WORKFLOW.md for Granian/E2E/subprocess/WebSocket/restart/cleanup overlap. Reviewed OOMPAH-490, OOMPAH-499, OOMPAH-500, and OOMPAH-172 in full. tests/test_granian_e2e.py owns the relevant helpers at lines 159-199, a function-scoped server fixture at line 215, and granular HTTP/WS/broadcast/restart classes from line 246 onward. Git history shows 9a68325e8 added 20 tests, 2821053d9 bounded complete WS draining, and 3c992af47 moved to per-test subprocesses to prevent a close/handshake edge case from hanging later tests.
3. Remaining work/risks: Consolidate to no more than six independent scenarios without reverting to one shared module process. Preserve complete initial WS push/draining and isolate each scenario with bounded SIGINT/terminate/kill plus pipe draining on all exits. Capture before/after collection and timing, repeat the file including pytest -x, check for leaked generated-script children, and run make test now that prerequisite OOMPAH-491 is Done. Do not weaken Granian parity or unit lifecycle tests.
4. Recommended next focus: test, for scenario refactoring and subprocess-cleanup verification. No files were changed and no tests were run during duplicate screening.
---
<!-- COMMENTS:END -->
