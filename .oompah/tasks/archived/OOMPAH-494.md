---
id: OOMPAH-494
type: task
status: Archived
priority: 1
title: Consolidate Granian subprocess tests into complete scenarios
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:53:29.472352Z'
updated_at: '2026-08-04T18:05:43.949296Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: e0f0b0bd-fe96-425b-9c9a-4dc2b317dee3
oompah.work_branch: epic-OOMPAH-490
oompah.task_costs:
  total_input_tokens: 517921
  total_output_tokens: 19897
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 517921
      output_tokens: 19897
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 517867
    output_tokens: 4905
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:32:19.590110+00:00'
  - profile: standard
    model: unknown
    input_tokens: 21
    output_tokens: 14036
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:42:24.437692+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 33
    output_tokens: 956
    cost_usd: 0.0
    recorded_at: '2026-08-04T18:05:41.576050+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-34126c5f87b1: '2026-08-04T18:05:18.010567+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-494
    target_state: Archived
    evidence_fingerprint: a8906a5bf81696794eaa747a05560beafe444d92072d41204b307dbeffe2c2d8
    audit_ids:
    - audit-83dd4686cc21
    kind: result
    applied: true
    retired_at: '2026-08-04T18:05:18.010574+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-494
    audit_id: audit-83dd4686cc21
    attempt_id: attempt-34126c5f87b1
    target_state: Archived
    evidence_fingerprint: a8906a5bf81696794eaa747a05560beafe444d92072d41204b307dbeffe2c2d8
    status: Archived
    audit_ids:
    - audit-83dd4686cc21
    applied: true
    created_at: '2026-08-04T18:05:18.010586+00:00'
    applied_at: '2026-08-04T18:05:27.163621+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-83dd4686cc21
    project_id: proj-14849f1b
    task_id: OOMPAH-494
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a8906a5bf81696794eaa747a05560beafe444d92072d41204b307dbeffe2c2d8
    attempts:
    - version: 1
      attempt_id: attempt-34126c5f87b1
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: a8906a5bf81696794eaa747a05560beafe444d92072d41204b307dbeffe2c2d8
      created_at: '2026-08-04T18:03:02.381038+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T18:03:02.381038+00:00'
      branch_key: epic-OOMPAH-490
      verdict: pass
      completed_at: '2026-08-04T18:05:18.010459+00:00'
      ended_at: '2026-08-04T18:05:18.010459+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T17:26:13.493645+00:00'
    updated_at: '2026-08-04T18:05:18.010459+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-34126c5f87b1
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a8906a5bf81696794eaa747a05560beafe444d92072d41204b307dbeffe2c2d8
    created_at: '2026-08-04T18:03:02.381038+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T18:03:02.381038+00:00'
    branch_key: epic-OOMPAH-490
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
author: oompah
created: 2026-07-28 15:32
---
Agent completed successfully in 155s (522772 tokens)
---
author: oompah
created: 2026-07-28 15:32
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 27
- Tokens: 517.9K in / 4.9K out [522.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 35s
- Log: OOMPAH-494__20260728T152947Z.jsonl
---
author: oompah
created: 2026-07-28 15:32
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 15:32
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-28 15:32
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-28 15:32
---
Understanding: I am the Test Engineer for OOMPAH-494. My task is to refactor tests/test_granian_e2e.py to consolidate its 20 function-scoped subprocess-per-test cases into no more than 6 scenario tests. Each scenario will own its own server lifecycle via a bounded context manager (SIGINT/terminate/kill + pipe draining). The four required scenarios are: (1) HTTP root/state contract, (2) WebSocket initial state/issues push, (3) two-client broadcast fan-out, (4) restart + HTTP/WS verification. I will preserve all existing behavioral contracts, verify no leaked subprocesses, and record before/after collection counts and timing.
---
author: oompah
created: 2026-07-28 15:35
---
Discovery: Current state confirmed - 20 tests in ~53s. Breakdown: 7 HTTP tests + 7 WS push tests + 3 broadcast tests + 3 restart tests, all using a function-scoped fixture that starts a new Granian subprocess per test (17 fixture-managed + 6 self-managed in restart tests = 23 total server startups). Plan: Refactor to 4 scenario tests via a _granian_server() context manager (always drains pipes + SIGINT→terminate→kill). Scenarios: (1) HTTP root/state contract combining all 7 HTTP assertions, (2) WS initial push combining all 6 WS push assertions, (3) broadcast fan-out combining all 3 broadcast assertions, (4) restart + HTTP + WS combining 3 restart assertions. Sequential multi-client test omitted as its coverage is subsumed by scenarios 2 and 3.
---
author: oompah
created: 2026-07-28 15:41
---
Implementation: Refactored tests/test_granian_e2e.py. Key changes: (1) Replaced function-scoped granian_e2e_base_url fixture with _granian_server() context manager that centralizes process ownership with always-run bounded SIGINT→terminate→kill cleanup plus pipe draining on all exits including assertion failure. (2) Consolidated 20 tests into 4 scenario functions: test_http_root_and_state_contract (7 HTTP assertions in 1 server start), test_ws_connection_and_initial_push (6 WS assertions in 1 server start), test_ws_broadcast_fan_out (3 broadcast assertions in 1 server start), test_restart_http_and_ws_contract (3 restart assertions with 2 server starts). All original behavioral contracts preserved. Sequential multi-client scenario omitted as subsumed by scenarios 2+3.
---
author: oompah
created: 2026-07-28 15:41
---
Verification: PASSED. Before: 20 tests in 52.97s. After: 4 tests in 5.35s (10x faster). No subprocess leaks confirmed (pgrep after both plain and -x runs shows zero Granian e2e processes). make test: 12345 passed, 7 skipped, 11 warnings in 238s - all unaffected. test_granian_parity.py and test_ws_lifecycle.py unchanged and passing. Acceptance criteria met: all contracts asserted, cases reduced 20→4 (≤6), one server per independent scenario, cleanup leaves no subprocess, runtime decreased materially.
---
author: oompah
created: 2026-07-28 15:42
---
Completion: tests/test_granian_e2e.py refactored and committed (14a319df7). Delivered: 4 scenario tests (down from 20), 5.35s runtime (down from 52.97s, 10x improvement), _granian_server() context manager with SIGINT→terminate→kill + pipe-drain cleanup on all exit paths, zero subprocess leaks verified, all 12345 tests passing in make test, test_granian_parity.py and test_ws_lifecycle.py untouched.
---
author: oompah
created: 2026-07-28 15:42
---
Refactored tests/test_granian_e2e.py: 20 tests → 4 scenario tests, 52.97s → 5.35s (10x faster). _granian_server() context manager centralises SIGINT→terminate→kill cleanup with pipe draining. No subprocess leaks. All 12345 tests pass.
---
author: oompah
created: 2026-07-28 15:42
---
Agent completed successfully in 596s (14057 tokens)
---
author: oompah
created: 2026-07-28 15:42
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/default]
- Turns: 45, Tool calls: 23
- Tokens: 21 in / 14.0K out [14.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 9m 56s
- Log: OOMPAH-494__20260728T153231Z.jsonl
---
author: oompah
created: 2026-08-04 17:26
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 18:03
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 18:03
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 18:05
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- merge_commit: 14a319df71780c96d2b5918ebbb50ba84662241e
- merge_on_main: true
- scenario_test_count: 4
- context_manager_present: _granian_server (contextlib.contextmanager)
- cleanup_bounded: stop_owned_process(timeout_s=8) + communicate(timeout=2) in finally
- parity_suite_untouched_by_task: tests/test_granian_parity.py last touched by OOMPAH-652 / TASK-472.5, not OOMPAH-494
- lifecycle_suite_untouched_by_task: tests/test_ws_lifecycle.py last touched by OOMPAH-691 (and older), not OOMPAH-494
- files_changed_in_task_commit: 1 (tests/test_granian_e2e.py, +246/-361)
---
author: oompah
created: 2026-08-04 18:05
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 18
- Tokens: 33 in / 956 out [989 total]
- Cost: $0.0000
- Exit: terminated, Duration: 2m 34s
- Log: OOMPAH-494__20260804T180320Z.jsonl
---
<!-- COMMENTS:END -->
