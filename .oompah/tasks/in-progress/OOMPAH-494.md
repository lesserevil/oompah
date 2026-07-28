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
labels: []
assignee: null
created_at: '2026-07-28T13:53:29.472352Z'
updated_at: '2026-07-28T15:31:43.077710Z'
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
<!-- COMMENTS:END -->
