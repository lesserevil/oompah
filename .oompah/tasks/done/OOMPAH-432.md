---
id: OOMPAH-432
type: bug
status: Done
priority: 2
title: "[backend:orchestrator] Dispatch loop stale but 4 agent(s) are active \u2014\
  \ skipping auto-restart to avoid killing in-flight work. Restart manually when agents\
  \ complete."
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-23T22:58:15.387967Z'
updated_at: '2026-07-24T01:08:20.766922Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#546
  owner: lesserevil
  repo: oompah
  number: '546'
  url: https://github.com/lesserevil/oompah/issues/546
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: In Progress
  last_synced_at: '2026-07-24T00:51:01.232189+00:00'
oompah.intake:
  missing_fields: []
  scope: small
  requestor_approved: false
  requestor_approved_at: null
  requestor_actor: null
  owner_override: false
  owner_override_at: null
  owner_actor: null
  decomposition_status: not_needed
  proposal_fingerprint: null
  last_validator_result: pass
  last_validated_at: '2026-07-23T22:58:20.414521+00:00'
oompah.agent_run_id: 290e4076-ecb4-4eab-8279-5eb430e0abe4
oompah.task_costs:
  total_input_tokens: 72
  total_output_tokens: 15997
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 72
      output_tokens: 15997
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 44
    output_tokens: 9442
    cost_usd: 0.0
    recorded_at: '2026-07-24T00:54:24.272042+00:00'
  - profile: deep
    model: unknown
    input_tokens: 28
    output_tokens: 6555
    cost_usd: 0.0
    recorded_at: '2026-07-24T01:08:19.302687+00:00'
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Dispatch loop stale but 4 agent(s) are active — skipping auto-restart to avoid killing in-flight work. Restart manually when agents complete.

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Dispatch loop stale but 4 agent(s) are active — skipping auto-restart to avoid killing in-flight work. Restart manually when agents complete.

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: ac6326253c85b77b
- dedup_fingerprint: ac6326253c85b77b
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/546
- Requestor: @NVShawn
- Reference: lesserevil/oompah#546

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-24 00:50
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-24 00:50
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-24 00:50
---
Understanding: This issue reports that the `backend:orchestrator` dispatch loop became stale while 4 agents were active. The system skipped auto-restart to avoid killing in-flight work and logged this as an error, which `error_watcher` auto-filed as a task. My role is Duplicate Investigator — I will search existing tasks for the same root cause before any implementation work proceeds.
---
author: oompah
created: 2026-07-24 00:54
---
Focus handoff: duplicate_detector

**Outcome:** No duplicate found. OOMPAH-432 is a unique, non-duplicated bug.

**Evidence reviewed:**
- Searched all .oompah/tasks/ (archived, done, merged, open, backlog) directories for: 'dispatch loop stale', 'Dispatch loop stale', 'skipping auto-restart', 'in-flight work', 'ac6326253c85b77b' (fingerprint), 'backend:orchestrator', 'recover_stale', 'dispatch_stale'
- No match found for the exact error message or fingerprint in any existing task
- Reviewed 200+ tasks across all states

**Root cause identified (oompah/orchestrator.py):**
- Method `recover_stale_dispatch_loop()` (line ~2527) contains the exact error message at lines 2551-2553
- When the dispatch loop is stale AND there are active agents, it calls `logger.error(...)` which triggers ErrorWatcher auto-filing
- The adjacent method `_arm_dispatch_stale_alert()` (line ~2477) already has explicit logic to use `logger.warning` instead of `logger.error` *specifically* to avoid ErrorWatcher filing — but `recover_stale_dispatch_loop()` was not updated with the same treatment

**Closest reviewed tasks (all confirmed distinct):**
- OOMPAH-265 (Merged): push-race TrackerError reaching error_watcher — different root cause (git push race), different module (oompah_md_tracker.py)
- OOMPAH-268 (Merged): git index.lock contention error_watcher filing — different root cause (git lock), same error_watcher pattern but different code path
- OOMPAH-177 (Archived): dispatch loop / ReleaseAddendumQueue — related to orchestrator dispatch loop but about addendum queue implementation, not stale-loop logging level
- OOMPAH-282 (Backlog): state_branch_migration UnicodeEncodeError — different module and error

**Remaining work:** Fix `recover_stale_dispatch_loop()` in oompah/orchestrator.py to downgrade the log level from `logger.error` to `logger.warning` for the 'skipping auto-restart' branch (agents active). This is already the intended behavior per the comment in `_arm_dispatch_stale_alert()`. Add a regression test. The fix prevents ErrorWatcher from auto-filing this operational decision as a bug.

**Recommended next focus:** chore (one-line log-level fix in oompah/orchestrator.py recover_stale_dispatch_loop + regression test)
---
author: oompah
created: 2026-07-24 00:54
---
Agent completed successfully in 230s (9486 tokens)
---
author: oompah
created: 2026-07-24 00:54
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 84, Tool calls: 61
- Tokens: 44 in / 9.4K out [9.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 50s
- Log: OOMPAH-432__20260724T005036Z.jsonl
---
author: oompah
created: 2026-07-24 00:54
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-24 01:00
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-24 01:00
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-07-24 01:00
---
Understanding (Maintenance Engineer): The duplicate_detector agent identified the root cause in oompah/orchestrator.py. The method recover_stale_dispatch_loop() uses logger.error() when the dispatch loop is stale but active agents prevent auto-restart. This triggers error_watcher to auto-file a bug. The fix is a one-line log-level downgrade from logger.error to logger.warning in that specific branch, plus a regression test. Proceeding with the fix now.
---
author: oompah
created: 2026-07-24 01:01
---
Discovery: Confirmed root cause in oompah/orchestrator.py recover_stale_dispatch_loop() (~line 2549). When running_count > 0, it calls logger.error() which triggers ErrorWatcher to auto-file this bug. The adjacent _arm_dispatch_stale_alert() method (line ~2514) explicitly uses logger.warning for the same reason — its comment says: 'log the first occurrence as a warning so ErrorWatcher (which files ERROR+ records) does not create a task for a condition the supervisor is already handling.' The recover_stale_dispatch_loop() was not given the same treatment. Fix: change logger.error to logger.warning in the running_count > 0 branch.
---
author: oompah
created: 2026-07-24 01:06
---
Implementation: In oompah/orchestrator.py recover_stale_dispatch_loop(), changed logger.error() to logger.warning() in the running_count > 0 branch. Updated the comment to explain the rationale (matching the existing explanation in _arm_dispatch_stale_alert()). Added regression test test_skips_restart_logs_warning_not_error_with_active_agents in tests/test_dispatch_loop_heartbeat.py that verifies: (1) the 'skipping auto-restart' message is logged at WARNING level, (2) ErrorWatcher.create_issue is NOT called. This directly prevents error_watcher from auto-filing this operational decision as a bug.
---
author: oompah
created: 2026-07-24 01:07
---
Verification: Ran make test — 12069 passed, 39 skipped, 0 failed. Ran tests/test_dispatch_loop_heartbeat.py in isolation — 42 passed (including new regression test test_skips_restart_logs_warning_not_error_with_active_agents). No regressions.
---
author: oompah
created: 2026-07-24 01:07
---
Completion: Fixed OOMPAH-432 by downgrading logger.error() to logger.warning() in recover_stale_dispatch_loop() (oompah/orchestrator.py) for the 'agents active, skipping auto-restart' branch. This prevents error_watcher from auto-filing routine operational decisions as bug tasks. Added regression test (17) in tests/test_dispatch_loop_heartbeat.py. All 12069 tests pass. Branch OOMPAH-432 pushed to origin.
---
author: oompah
created: 2026-07-24 01:07
---
Downgraded logger.error to logger.warning in recover_stale_dispatch_loop() for the agents-active branch. Prevents error_watcher from auto-filing this operational decision as a bug. Added regression test. All 12069 tests pass.
---
author: oompah
created: 2026-07-24 01:08
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 25
- Tokens: 28 in / 6.6K out [6.6K total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 49s
- Log: OOMPAH-432__20260724T010034Z.jsonl
---
<!-- COMMENTS:END -->
