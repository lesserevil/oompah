---
id: OOMPAH-403
type: bug
status: Merged
priority: 0
title: '[backend:orchestrator] Worker did not stop within 10000ms; continuing shutdown
  issue_identifier=OOMPAH-339'
parent: null
children: []
blocked_by: []
labels:
- external:github
- focus-complete:duplicate_detector
- ci-fix
assignee: null
created_at: '2026-07-22T05:35:11.758325Z'
updated_at: '2026-07-22T06:32:42.529711Z'
work_branch: OOMPAH-403
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/532
review_number: '532'
merged_at: null
oompah.external.github:
  id: lesserevil/oompah#531
  owner: lesserevil
  repo: oompah
  number: '531'
  url: https://github.com/lesserevil/oompah/issues/531
  requestor_login: NVShawn
  imported_comment_ids: []
  last_synced_status: Merged
  last_synced_at: '2026-07-22T06:32:41.839689+00:00'
  last_github_state: closed
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
  last_validated_at: '2026-07-22T05:35:18.775008+00:00'
oompah.agent_run_id: 77aa71cc-3ad0-4ea4-a2b2-380e5ac2a500
oompah.task_costs:
  total_input_tokens: 1191809
  total_output_tokens: 19361
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 1191809
      output_tokens: 19361
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 40
    output_tokens: 7393
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:42:56.405887+00:00'
  - profile: default
    model: unknown
    input_tokens: 1191605
    output_tokens: 6849
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:46:38.515540+00:00'
  - profile: deep
    model: unknown
    input_tokens: 74
    output_tokens: 2105
    cost_usd: 0.0
    recorded_at: '2026-07-22T05:55:49.840763+00:00'
  - profile: deep
    model: unknown
    input_tokens: 90
    output_tokens: 3014
    cost_usd: 0.0
    recorded_at: '2026-07-22T06:26:55.847770+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/532
oompah.review_number: '532'
oompah.work_branch: OOMPAH-403
oompah.target_branch: main
---
## Summary

### Problem

Oompah detected a backend error from `backend:orchestrator`:

> Worker did not stop within 10000ms; continuing shutdown issue_identifier=OOMPAH-339

### Desired Behavior

The operation in `backend:orchestrator` should complete successfully, or degrade gracefully with a clear actionable message. No unhandled error should be auto-filed as a task during normal operation.

### Steps to Reproduce

1. Run oompah with `backend:orchestrator` active.
2. Let oompah execute the operation that involves `backend:orchestrator` (tracker: `github_issues:lesserevil/oompah`).
3. Observe that the error is captured by `error_watcher` and auto-filed as this task.

### Actual Behavior

An error occurs in `backend:orchestrator` and is recorded by oompah's `error_watcher`:

> Worker did not stop within 10000ms; continuing shutdown issue_identifier=OOMPAH-339

### Acceptance Criteria

- The error from `backend:orchestrator` no longer occurs, or is handled gracefully so `error_watcher` is not triggered.
- The root cause is identified and resolved, or documented as a known acceptable failure with explicit handling.
- No regression: other error types continue to be reported correctly by `error_watcher`.

---
*Auto-filed by oompah error_watcher*
- source_project: global
- tracker: github_issues:lesserevil/oompah
- tracker_kind: github_issues
- fingerprint: 93c60c1dea846b57
- dedup_fingerprint: 93c60c1dea846b57
- tracker_owner: lesserevil
- tracker_repo: oompah

## External GitHub Issue

- URL: https://github.com/lesserevil/oompah/issues/531
- Requestor: @NVShawn
- Reference: lesserevil/oompah#531

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 05:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-22 05:35
---
Understanding: This issue is an auto-filed error report from the error_watcher. The error 'Worker did not stop within 10000ms; continuing shutdown' occurred in backend:orchestrator while processing OOMPAH-339. My role is Duplicate Investigator — I need to determine if this shutdown timeout issue is already tracked in an existing task. Plan: (1) Search .oompah/tasks for 'worker', 'shutdown', 'timeout', and 'stop within' keywords; (2) View OOMPAH-339 for context; (3) Check for any existing tasks covering the same shutdown timeout problem.
---
author: oompah
created: 2026-07-22 05:42
---
Discovery: OOMPAH-403 is NOT a duplicate. Duplicate screening complete.

**Root cause identified:**
The error originates in oompah/orchestrator.py line 18906 where logger.error() logs 'Worker did not stop within Xms; continuing shutdown issue_identifier=OOMPAH-339'. This is logged when the orchestrator cancels a running worker task for OOMPAH-339 during shutdown and the worker doesn't complete cancellation within worker_termination_timeout_ms (10000ms default). The logger.error() call is what triggers error_watcher to auto-file this task.

Looking at OOMPAH-339's comment history, there were multiple 'terminated' exit events (comments #57 and #64) where workers were killed mid-run, which is the scenario that triggers this code path.

**Search scope:**
- All .oompah/tasks/ states: archived (225+), merged (53+), done (1), open (1), backlog (1)
- Searched: 'stop within', '10000ms', 'did not stop', 'Worker did not stop', 'backend:orchestrator', 'shutdown.*worker', 'worker.*shutdown'
- All returned zero results

**Closest candidates reviewed (NOT duplicates):**
- OOMPAH-339 (In Progress): This is the SUBJECT of the error (the worker that wouldn't stop), not a duplicate. OOMPAH-339 is about GitLab status-label governance — a completely different concern.
- OOMPAH-282 (Backlog): Different auto-filed error (UnicodeEncodeError in state_branch_migration), same error_watcher mechanism but different root cause.
- OOMPAH-118/188/113/161: Other auto-filed errors from backend:webhooks and backend:server — different backends and different error conditions.

**Root cause options for the implementation agent:**
1. Downgrade logger.error() → logger.warning() at orchestrator.py:18906 so error_watcher doesn't file tasks for expected shutdown timeouts
2. Increase worker_termination_timeout_ms (configurable via .env) to give long-running agent processes more time to exit cleanly
3. Filter this specific error class in error_watcher to suppress known-acceptable shutdown noise

Key file: oompah/orchestrator.py ~line 18890-18930 (the _cancel_running_worker or similar method)
---
author: oompah
created: 2026-07-22 05:42
---
Focus handoff: duplicate_detector

1. **Outcome:** OOMPAH-403 is NOT a duplicate. No existing task covers the 'Worker did not stop within 10000ms; continuing shutdown' error from backend:orchestrator.

2. **Evidence:**
   - Searched all 280+ tasks across all states for keywords: stop within, 10000ms, did not stop, Worker, backend:orchestrator, shutdown+worker, worker+shutdown
   - All searches returned zero results
   - Confirmed error source: oompah/orchestrator.py line 18906, logger.error() call inside worker cancellation wait block
   - Code context (lines 18890-18930): orchestrator cancels worker_task on shutdown, waits up to worker_termination_timeout_ms (default 10000ms), logs ERROR if task doesn't finish in time

3. **Key files:**
   - oompah/orchestrator.py ~line 18890-18930: the worker shutdown block with logger.error() that triggers error_watcher
   - .env.example: OOMPAH_WORKER_TERMINATION_TIMEOUT_MS if configurable
   - oompah/error_watcher.py or similar: error classification logic

4. **Root cause options for implementation:**
   - Option A (preferred): Downgrade logger.error() → logger.warning() for the shutdown timeout case — this is expected behavior during a hard kill of a long-running agent, not an actionable error
   - Option B: Add a filter in error_watcher to suppress 'Worker did not stop within' as a known-acceptable shutdown event
   - Option C: Increase worker_termination_timeout_ms default or document OOMPAH_WORKER_TERMINATION_TIMEOUT_MS in .env.example

5. **Remaining work:** Fix the log level or error_watcher filter so this expected shutdown event doesn't get auto-filed as a bug. Add a regression test confirming the fix.

6. **Recommended next focus:** chore (log level fix is a small cleanup) or feature (if error_watcher filter needs design)
---
author: oompah
created: 2026-07-22 05:42
---
Agent completed successfully in 442s (7433 tokens)
---
author: oompah
created: 2026-07-22 05:42
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 52, Tool calls: 37
- Tokens: 40 in / 7.4K out [7.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 7m 22s
- Log: OOMPAH-403__20260722T053536Z.jsonl
---
author: oompah
created: 2026-07-22 05:43
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-22 05:43
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-22 05:43
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-22 05:46
---
Agent completed successfully in 214s (1198454 tokens)
---
author: oompah
created: 2026-07-22 05:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 25
- Tokens: 1.2M in / 6.8K out [1.2M total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 34s
- Log: OOMPAH-403__20260722T054306Z.jsonl
---
author: oompah
created: 2026-07-22 05:46
---
Agent completed without closing this issue (214s (1198454 tokens)). Escalating from 'default' to 'deep'. Retrying in 10s (1/3).
---
author: oompah
created: 2026-07-22 05:47
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 05:47
---
Focus: Software Engineer
---
author: oompah
created: 2026-07-22 05:47
---
Understanding (continuation run): Picking up from prior agents. Root cause confirmed: oompah/orchestrator.py logs at ERROR level when a worker doesn't stop within the termination timeout during shutdown. This triggers error_watcher to auto-file bugs. The fix is to downgrade this specific log from ERROR to WARNING, since a worker not stopping within 10s during shutdown is an expected/acceptable condition (not an actionable error). Plan: (1) Find the exact code, (2) change logger.error → logger.warning, (3) add a regression test, (4) run make test, (5) commit and close.
---
author: oompah
created: 2026-07-22 05:54
---
Discovery: Confirmed root cause. In oompah/orchestrator.py, the _terminate_running() method calls logger.error() when a worker task does not complete within worker_termination_timeout_ms (default 10000ms). The error_watcher logging handler is installed at logging.ERROR level, so this log call triggers it to auto-file a bug task. This is expected behavior during shutdown (e.g., when an agent process is hard-killed), not an actionable error requiring a bug report.
---
author: oompah
created: 2026-07-22 05:54
---
Implementation: Changed logger.error() → logger.warning() in oompah/orchestrator.py _terminate_running() for the worker-shutdown timeout path. Since error_watcher only captures ERROR+ log records, this prevents spurious bug auto-filing for expected shutdown timeouts. Added regression test test_shutdown_timeout_logs_warning_not_error in tests/test_task_cost_telemetry.py that patches asyncio.wait to force the timeout path and asserts the log record is at WARNING level. All 39 cost telemetry tests + 130 error_watcher tests pass.
---
author: oompah
created: 2026-07-22 05:55
---
Verification: All relevant tests pass.
- tests/test_task_cost_telemetry.py: 39/39 passed (including new regression test)
- tests/test_error_watcher.py + test_error_watcher_orchestrator.py: 130/130 passed
The new test test_shutdown_timeout_logs_warning_not_error confirms the shutdown-timeout message is logged at WARNING (not ERROR). The 8 pre-existing failures are unrelated to this change (test_intake_promotion, test_server_epic_state, test_transition_gate).
---
author: oompah
created: 2026-07-22 05:55
---
Completion: Fixed OOMPAH-403. Changed logger.error() → logger.warning() in oompah/orchestrator.py _terminate_running() (the worker-shutdown timeout path). error_watcher captures only ERROR+ records, so this change prevents it from auto-filing spurious bug tasks when a worker doesn't stop within the termination timeout — an expected condition during hard kills. Added regression test to prevent recurrence. Branch OOMPAH-403 pushed and up to date.
---
author: oompah
created: 2026-07-22 05:55
---
Changed logger.error → logger.warning in orchestrator._terminate_running() for the worker-shutdown timeout path. error_watcher only captures ERROR+ records, so this prevents spurious auto-filed bug tasks for expected shutdown timeouts. Added regression test test_shutdown_timeout_logs_warning_not_error.
---
author: oompah
created: 2026-07-22 05:55
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 37
- Tokens: 74 in / 2.1K out [2.2K total]
- Cost: $0.0000
- Exit: terminated, Duration: 8m 48s
- Log: OOMPAH-403__20260722T054706Z.jsonl
---
author: oompah
created: 2026-07-22 06:01
---
YOLO: CI tests failed on MR #532. Fix the failing tests so this MR can merge. Do NOT rewrite the feature — only fix test failures. IMPORTANT: Paths in CI logs are not trustworthy. Run tests locally to get accurate paths and errors.
---
author: oompah
created: 2026-07-22 06:09
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-22 06:09
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-22 06:10
---
Understanding: CI Failure Fixer role. CI failed on PR #532 (Python 3.13 job). 7 tests failed, all with 422 responses when other codes were expected:
- test_intake_promotion.py::test_api_rejects_direct_proposed_to_open_transition (422 != 409)
- test_server_epic_state.py (3 failures, 422 != 200/409)
- test_transition_gate.py (3 failures, 422 != 403/200)

Branch diff shows only 2 files changed: oompah/orchestrator.py (logger.error→warning) and tests/test_task_cost_telemetry.py (regression test). The failures are in unrelated test files. Plan: (1) run failing tests locally to reproduce, (2) check if failures pre-exist on main, (3) determine if something in our diff is causing them, (4) fix minimally.
---
author: oompah
created: 2026-07-22 06:21
---
Discovery: Root cause of 7 CI failures confirmed. Commit dcbef393e ('Preserve structured native task descriptions') added a description validation to api_update_issue() in server.py that returns 422 when trying to promote to a dispatchable status (Open, Needs CI Fix, Needs Rebase) without a description. The failing tests create Issue objects via helper functions (_issue(), _make_issue()) without descriptions, so the 422 validation fires before the actual logic being tested. The fix is minimal: add description='Implementation details' to the Issue factory helpers in the 3 failing test files. These failures pre-exist on main — our orchestrator.py change did not cause them, but they block the PR from merging.
---
author: oompah
created: 2026-07-22 06:22
---
Implementation: Fixed 7 CI failures in PR #532 by adding non-empty description fields to Issue helper factories in 3 test files:
- tests/test_intake_promotion.py: inline Issue in test_api_rejects_direct_proposed_to_open_transition
- tests/test_transition_gate.py: _issue() helper
- tests/test_server_epic_state.py: _make_issue() helper

Root cause: commit dcbef393e added server-side validation returning 422 when promoting to a dispatchable status without a description. Test helpers created Issue objects without descriptions, so the 422 fired before the tested logic was reached.

The OOMPAH-403 feature change (orchestrator.py logger.error→warning + regression test) is completely separate and unrelated to these failures.
---
author: oompah
created: 2026-07-22 06:22
---
YOLO: merged PR #532.
---
author: oompah
created: 2026-07-22 06:26
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/default]
- Turns: 0, Tool calls: 57
- Tokens: 90 in / 3.0K out [3.1K total]
- Cost: $0.0000
- Exit: terminated, Duration: 17m 20s
- Log: OOMPAH-403__20260722T060938Z.jsonl
---
<!-- COMMENTS:END -->
