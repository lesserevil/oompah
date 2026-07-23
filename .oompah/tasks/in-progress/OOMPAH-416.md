---
id: OOMPAH-416
type: task
status: In Progress
priority: 0
title: Post REFRESH_REQUESTED after orphan resets to wake dispatch immediately
parent: OOMPAH-414
children: []
blocked_by: []
labels:
- focus-complete:duplicate_detector
- ci-fix
assignee: null
created_at: '2026-07-23T19:34:30.939292Z'
updated_at: '2026-07-23T20:52:09.681618Z'
work_branch: epic-OOMPAH-414
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: fff6ee95-7903-4f89-9b24-8051cba6ecd4
oompah.work_branch: epic-OOMPAH-414
oompah.task_costs:
  total_input_tokens: 409032
  total_output_tokens: 9216
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 409032
      output_tokens: 9216
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 21
    output_tokens: 4995
    cost_usd: 0.0
    recorded_at: '2026-07-23T20:12:11.469410+00:00'
  - profile: standard
    model: unknown
    input_tokens: 409011
    output_tokens: 4221
    cost_usd: 0.0
    recorded_at: '2026-07-23T20:24:14.898021+00:00'
---
## Summary

### Problem

_reset_orphaned_in_progress() (called in step 5c, fire-and-forget from the thread pool) resets orphaned In Progress tasks back to Open, but never notifies the dispatch loop. The dispatch loop only picks up the newly eligible tasks on the next full tick. During the July 23 incident, maintenance reset EXOCOMP-7 and EXOCOMP-41 *after* dispatch had already selected candidates, so they had to wait another full_sync_interval_ms (5 min) before dispatch. Operators patched this by manually POSTing /api/v1/refresh.

### Scope

In oompah/orchestrator.py, in the _reset_orphaned_in_progress() method:
- Track whether any issue was successfully reset (i.e., tracker.update_issue was called without exception and the issue was not preserved as Done).
- After the main reset loop, if any_reset is True, call: self._post_event(DispatchEvent(event_type=DispatchEventType.REFRESH_REQUESTED))
- _post_event is already thread-safe (uses loop.call_soon_threadsafe when called from a background thread), so no additional locking is needed.
- Add a logger.info line to make the wake visible in logs: 'Orphan reset: %d issue(s) returned to Open — posting REFRESH_REQUESTED to wake dispatch immediately'

### Tests

Add a test in tests/test_dispatch_loop_heartbeat.py (or a new test file tests/test_orphan_reset_dispatch_wake.py):
- Test that _reset_orphaned_in_progress() posts exactly one REFRESH_REQUESTED event when at least one orphan is reset.
- Test that no REFRESH_REQUESTED event is posted when no orphans were reset (empty candidates, no in_progress issues).
- Mock tracker.update_issue and verify the event posting behavior.

Run make test before committing.

### Acceptance

After orphan resets, the dispatch loop wakes within milliseconds (via REFRESH_REQUESTED) rather than waiting for the next full tick (up to full_sync_interval_ms = 5 min). Newly-open Exocomp tasks are dispatched in the same tick or the immediately-following refresh tick, not on the next scheduled tick.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 20:02
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-23 20:02
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-23 20:11
---
Focus handoff: duplicate_detector

1. **Outcome:** No duplicate found. OOMPAH-416 is a unique, first-of-its-kind task.

2. **Investigation scope:**
   - Searched all .oompah/tasks/ states (open, backlog, done, merged, archived) — 280+ tasks total
   - Grep patterns: orphan, REFRESH_REQUESTED, reset_orphaned, dispatch wake, _post_event, DispatchEventType, dispatch loop, heartbeat, full_sync
   - Reviewed docs/ and plans/ directories
   - Verified parent epic OOMPAH-414 and sibling tasks OOMPAH-415, OOMPAH-417

3. **Closest candidates reviewed and ruled out:**
   - OOMPAH-348 (Done): Scheduler wedge fixes — tracker timeouts, HTTP isolation, shutdown bounding. Did NOT add any orphan-reset dispatch wake.
   - OOMPAH-349/350/351/352 (Done): Children of OOMPAH-348 — tracker timeouts, event loop isolation, shutdown bounds, diagnostics. None touch _reset_orphaned_in_progress().
   - OOMPAH-406/407 (not found locally, referenced in epic): Changed stale diagnostic logging from ERROR to WARNING. Different scope entirely — logging, not dispatch wake.
   - OOMPAH-415 (In Progress, sibling): Decouples stale-dispatch threshold from full_sync_interval. Distinct from orphan-reset dispatch waking.
   - OOMPAH-417 (Open, sibling): Regression tests — depends on OOMPAH-415 and OOMPAH-416 being implemented first.

4. **Relevant files for implementation (identified by prior epic planner agent):**
   - oompah/orchestrator.py — _reset_orphaned_in_progress() method (add any_reset tracking + self._post_event(DispatchEvent(DispatchEventType.REFRESH_REQUESTED)))
   - tests/test_dispatch_loop_heartbeat.py or tests/test_orphan_reset_dispatch_wake.py — new tests

5. **Remaining work:** Full implementation per task description. _post_event() is already thread-safe.

6. **Recommended next focus:** feature
---
author: oompah
created: 2026-07-23 20:12
---
Agent completed successfully in 602s (5016 tokens)
---
author: oompah
created: 2026-07-23 20:12
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 47, Tool calls: 32
- Tokens: 21 in / 5.0K out [5.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 10m 2s
- Log: OOMPAH-416__20260723T200212Z.jsonl
---
author: oompah
created: 2026-07-23 20:12
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-23 20:14
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 20:14
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-23 20:19
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/default]
- Turns: 0, Tool calls: 26
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 5m 10s
- Log: OOMPAH-416__20260723T201416Z.jsonl
---
author: oompah
created: 2026-07-23 20:19
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 20:19
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-23 20:24
---
Agent completed successfully in 274s (413232 tokens)
---
author: oompah
created: 2026-07-23 20:24
---
Run #2 [attempt=2, profile=standard, role=standard -> Codex/default]
- Turns: 1, Tool calls: 6
- Tokens: 409.0K in / 4.2K out [413.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 34s
- Log: OOMPAH-416__20260723T201944Z.jsonl
---
author: oompah
created: 2026-07-23 20:24
---
Agent completed without closing this issue (274s (413232 tokens)). Escalating from 'standard' to 'deep'. Retrying in 20s (2/3).
---
author: oompah
created: 2026-07-23 20:26
---
Retrying (attempt #4, agent: deep)
---
author: oompah
created: 2026-07-23 20:26
---
Focus: Epic Planner
---
author: oompah
created: 2026-07-23 20:33
---
YOLO: CI tests failed on MR #543. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-23 20:36
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 20:36
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-23 20:39
---
Understanding (CI Failure Fixer): Found 4 failing tests on MR #543 (epic-OOMPAH-414 branch). Root causes:

1. tests/test_epic_strategy.py (2 tests) + tests/test_yolo_watchdog.py (1 test): The OOMPAH-415 commit added _mark_needs_human() helper that uses hasattr() duck-typing. With MagicMock, hasattr() always returns True, so tracker.mark_needs_human() is called instead of tracker.update_issue(). Tests still assert tracker.update_issue was called.

2. tests/test_scm.py::test_legacy_failure_short_circuits: When legacy combined-status is 'failure' (total_count=1) but check_runs is empty [], the code falls through to 'return passed, warnings' instead of honoring the legacy failure. The legacy_failure flag should gate this return.

Fix plan: (a) update epic_strategy+yolo_watchdog test assertions to use tracker.mark_needs_human; (b) fix scm.py empty-runs path to check legacy_failure before returning passed.
---
author: oompah
created: 2026-07-23 20:52
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-23 20:52
---
Focus: CI Failure Fixer
---
<!-- COMMENTS:END -->
