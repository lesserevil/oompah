---
id: OOMPAH-715
type: task
status: In Validation
priority: null
title: Make full-sync event-loop test deterministic under full-gate load
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T01:08:30.439967Z'
updated_at: '2026-08-03T02:01:01.904929Z'
work_branch: OOMPAH-715
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/672
review_number: '672'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6bd19602e6ff713923c7e4430956c6722b2579dc3876e25497aa6e6413b85557
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-03T01:10:10.602994+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-715 targets a specific test race in the event-driven\
    \ loop subsystem (full-sync event emission and consumption under load). The task\
    \ corpus contains no active duplicate: OOMPAH-715 is the sole Open task, and the\
    \ 60 Archived tasks (OOMPAH-156 onward) address tracker intake, epic workflows,\
    \ and release infrastructure\u2014distinct problem domains. No historical task\
    \ references `test_event_driven_loop.py`, `full_sync_loop_posts_full_sync_events`,\
    \ or event-driven loop test determinism.\nI'm being asked to investigate whether\
    \ OOMPAH-715 is a duplicate of an existing issue. Let me analyze the current task\
    \ and compare it against the project task corpus.\n\n## Task Analysis\n\n**OOMPAH-715**\
    \ is focused on:\n- Making a specific test deterministic: `tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_full_sync_loop_posts_full_sync_events`\n\
    - The test exhibits a load/timing-dependent race (fails under full parallel gate,\
    \ passes in isolation and 10 consecutive retries)\n- Core issue: implicit timing\
    \ windows and wall-clock assumptions in the test\n- Solution scope: reproduce\
    \ under delayed scheduling, replace sleeps with explicit synchronization, ensure\
    \ deterministic cleanup\n\n## Corpus Review\n\nI've reviewed all 175 tasks in\
    \ the provided corpus. Key findings:\n\n- **OOMPAH-715** is the only Open task\
    \ (all others from OOMPAH-160 through OOMPAH-175 are Archived)\n- The Archived\
    \ tasks cover:\n  - OOMPAH-156\u2013162: error_watcher deduplication, task archive\
    \ UI, GitHub intake parsing\n  - OOMPAH-163\u2013165: epic workflow fixes (stacked\
    \ children, generated branches, shared epic landing)\n  - OOMPAH-166\u2013171:\
    \ epic workflow standardization (remove flat/stacked strategies, draft lifecycle)\n\
    \  - OOMPAH-172\u2013175: release-branch addendums infrastructure\n\n**No task\
    \ in the corpus addresses event-driven loop test determinism.** The archived tasks\
    \ focus on tracker intake, epic workflows, and release infrastructure\u2014orthogonal\
    \ systems.\n\nThe closest related task by topic would be event-loop behavior,\
    \ but:\n- No other task mentions `test_event_driven_loop.py` or `test_full_sync_loop_posts_full_sync_events`\n\
    - No other task deals with mocked asyncio, event waiters, or full-sync scheduling\
    \ under load\n- No other task is about test race conditions in this subsystem\n\
    \n---\n\nFocus handoff: duplicate_detector\n\nDuplicate preflight verdict: no_duplicate\n\
    \nMatches: none\n\nEvidence: OOMPAH-715 targets a specific test race in the event-driven\
    \ loop subsystem (full-sync event emission and consumption under load"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: null
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1261
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1261
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1261
    cost_usd: 0.0
    recorded_at: '2026-08-03T01:10:10.598496+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-715__20260803T010945Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-715
    source_sha: 8b6f368252e653d56f0c1c9a07da0fc825a9cb10
    completed_at: '2026-08-03T01:10:10.618262+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-715
  head_sha: 27c62eca57fa115c3d22d2e4053181ae40fb1b8b
  submitted_at: '2026-08-03T01:24:19.381222+00:00'
  updated_at: '2026-08-03T01:24:19.381222+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/672
oompah.review_number: '672'
oompah.work_branch: OOMPAH-715
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-e01e7451d2c6: '2026-08-03T02:00:56.066450+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-715
    target_state: Done
    evidence_fingerprint: 09e5442de7f31e83999c19bf1df91acca1e17c15829442d27dc1bf3db064083c
    audit_ids:
    - audit-2005a0765e8c
    kind: result
    applied: true
    retired_at: '2026-08-03T02:00:56.066459+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-715
    audit_id: audit-2005a0765e8c
    attempt_id: attempt-e01e7451d2c6
    target_state: Done
    evidence_fingerprint: 09e5442de7f31e83999c19bf1df91acca1e17c15829442d27dc1bf3db064083c
    status: In Validation
    audit_ids:
    - audit-2005a0765e8c
    applied: true
    created_at: '2026-08-03T02:00:56.066468+00:00'
    applied_at: '2026-08-03T02:01:00.782794+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-2005a0765e8c
    project_id: proj-14849f1b
    task_id: OOMPAH-715
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 09e5442de7f31e83999c19bf1df91acca1e17c15829442d27dc1bf3db064083c
    attempts:
    - version: 1
      attempt_id: attempt-e01e7451d2c6
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 09e5442de7f31e83999c19bf1df91acca1e17c15829442d27dc1bf3db064083c
      created_at: '2026-08-03T01:59:38.006211+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T01:59:38.006211+00:00'
      branch_key: OOMPAH-715
      verdict: pass
      completed_at: '2026-08-03T02:00:56.066337+00:00'
      ended_at: '2026-08-03T02:00:56.066337+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T01:59:18.430597+00:00'
    updated_at: '2026-08-03T02:00:56.066337+00:00'
  - version: 1
    audit_id: audit-74fa6640743a
    project_id: proj-14849f1b
    task_id: OOMPAH-715
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 09e5442de7f31e83999c19bf1df91acca1e17c15829442d27dc1bf3db064083c
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T01:59:18.430597+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e01e7451d2c6
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 09e5442de7f31e83999c19bf1df91acca1e17c15829442d27dc1bf3db064083c
    created_at: '2026-08-03T01:59:38.006211+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T01:59:38.006211+00:00'
    branch_key: OOMPAH-715
---
## Summary

Triggered by the OOMPAH-711 exact-head branch gate on 2026-08-03. The full parallel make test run failed tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_full_sync_loop_posts_full_sync_events while nine other deterministic fixture failures were present. The exact event-loop test passed immediately afterward and passed ten consecutive isolated retries, identifying a load/timing-dependent test race rather than a stable OOMPAH-711 behavior regression.

Implementation scope:
- Reproduce the full-sync event posting failure under parallel or delayed scheduling and identify the implicit wall-clock, background-loop, or teardown assumption.
- Replace sleeps or timing windows with explicit synchronization around the full-sync event emission and consumption being asserted.
- Ensure every loop task, event waiter, executor, and mocked clock is deterministically quiesced at test teardown.
- Preserve production event-driven-loop timing and safety-net full-sync semantics.

Relevant code: tests/test_event_driven_loop.py TestRunEventDrivenLoop, oompah/orchestrator.py event-driven loop and full-sync scheduling, and shared asyncio fixtures. Gate evidence is recorded in OOMPAH-711 comment 15.

Required tests:
- Force delayed event-loop scheduling and prove the assertion waits for the exact full-sync event rather than elapsed wall time.
- Repeated parallel execution cannot reproduce the failure.
- Cancellation and shutdown leave no pending task or closed-loop subprocess/resource warning.
- Existing event-driven invalidation and safety-net tests remain green.

Acceptance criteria:
- Replaying the OOMPAH-711 full-gate load cannot fail this test from scheduling order.
- The test uses an explicit deterministic barrier and leaves no live background work.
- Production loop behavior is unchanged.
- Focused event-driven-loop tests and make test/check-secrets pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 01:08
---
Project owner promoted this race follow-up to Open. The exact test passed ten consecutive isolated retries after the OOMPAH-711 full-gate failure; implementation should reproduce delayed parallel scheduling and replace the implicit timing window with an explicit barrier.
---
author: oompah
created: 2026-08-03 01:09
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 01:09
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 01:10
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 30s
- Log: OOMPAH-715__20260803T010945Z.jsonl
---
author: oompah
created: 2026-08-03 01:10
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-03 01:10
---
Focus: Technical Writer
---
author: oompah
created: 2026-08-03 01:11
---
Understanding: The failure is a scheduling-sensitive async test race around the safety-net full-sync task. I will inspect the test's event observation and teardown, reproduce it with delayed scheduling/parallel workers, then add an explicit emission barrier and deterministic task cleanup while leaving orchestrator timing unchanged.
---
author: oompah
created: 2026-08-03 01:14
---
Verification: The focused full-sync test passes, the complete test_event_driven_loop.py module passes 60/60 serially, and three concurrent pytest-xdist runs each pass 60/60. The delayed-scheduling barrier test has not produced pending-task warnings.
---
author: oompah
created: 2026-08-03 01:24
---
Completion: Reworked tests/test_event_driven_loop.py::TestRunEventDrivenLoop::test_full_sync_loop_posts_full_sync_events to use explicit delayed-sleep, dispatch-queue, and second-emission barriers. Cleanup now cancels and drains the producer and queue waiter deterministically; production code is unchanged. Verified 60 event-loop tests serially, three concurrent xdist module runs (60/60 each), the full parallel runner (15,047 passed; 41 existing warnings), focused ResourceWarning/RuntimeWarning checks, and make check-secrets. Normal make test setup was blocked before pytest by this worker's uv DBus transient-scope error and managed CLI snapshot identity check; the exact underlying parallel runner passed. Commit was rebased and pushed as a1705bc7f-derived HEAD.
---
author: oompah
created: 2026-08-03 01:24
---
Deterministic full-sync event-loop test with explicit emission barriers and task teardown
---
author: oompah
created: 2026-08-03 01:24
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 45
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 14m 9s
- Log: OOMPAH-715__20260803T011037Z.jsonl
---
author: oompah
created: 2026-08-03 01:48
---
Branch quality gate passed for `27c62eca57fa115c3d22d2e4053181ae40fb1b8b` using `make test` in 417.1s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 01:48
---
Completion-audit guidance while the old service is deployed: use only approved read_file, list_files, search_files, and simple single read-only run_command calls. Do not use grep, shell pipes, redirection, command chaining, or whole-file reads. Exact head 27c62eca57fa115c3d22d2e4053181ae40fb1b8b passed the complete make test gate in 417.1s.
---
author: oompah
created: 2026-08-03 01:59
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 01:59
---
YOLO: merged PR #672.
---
author: oompah
created: 2026-08-03 01:59
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 01:59
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 02:00
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- exact_head: 27c62eca57fa115c3d22d2e4053181ae40fb1b8b
- merge_commit: ecf0582b9539ec71b8b63734cd1190e4f9c97453
- pr_number: 672
- files_changed: tests/test_event_driven_loop.py (+73/-19)
- production_diff: empty (oompah/orchestrator.py unchanged)
- branch_gate: make test PASS 417.1s for 27c62eca5
- barrier_primitives: asyncio.Event: sleep_started, release_sleep, second_full_sync_posted; patched asyncio.sleep with _delayed_sleep
- teardown: finally cancels producer_task and event_task, asyncio.gather(return_exceptions=True)
---
<!-- COMMENTS:END -->
