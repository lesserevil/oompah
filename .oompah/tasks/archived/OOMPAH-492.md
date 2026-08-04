---
id: OOMPAH-492
type: bug
status: Archived
priority: 1
title: Isolate worker-exit and epic-rebase tests from the live tracker
parent: OOMPAH-490
children: []
blocked_by:
- OOMPAH-491
labels:
- focus-complete:duplicate_detector
assignee: null
created_at: '2026-07-28T13:53:27.511520Z'
updated_at: '2026-08-04T18:02:36.486680Z'
work_branch: epic-OOMPAH-490
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 08675e3c-a8d0-43a7-aff6-520907bec104
oompah.work_branch: epic-OOMPAH-490
oompah.task_costs:
  total_input_tokens: 404924
  total_output_tokens: 59877
  total_cost_usd: 0.0
  by_model:
    unknown:
      input_tokens: 404924
      output_tokens: 59877
      cost_usd: 0.0
  runs:
  - profile: default
    model: unknown
    input_tokens: 404810
    output_tokens: 3022
    cost_usd: 0.0
    recorded_at: '2026-07-28T14:58:23.653994+00:00'
  - profile: deep
    model: unknown
    input_tokens: 89
    output_tokens: 51415
    cost_usd: 0.0
    recorded_at: '2026-07-28T15:18:52.663886+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 25
    output_tokens: 5440
    cost_usd: 0.0
    recorded_at: '2026-08-04T18:02:33.387738+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-d9c29717b1ff: '2026-08-04T18:02:07.533201+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-492
    target_state: Archived
    evidence_fingerprint: 1bbaa04aa66ecd8eaf48bb0793839eab1b78230b808d8890804a5605b55507bf
    audit_ids:
    - audit-19b7fc30a962
    kind: result
    applied: true
    retired_at: '2026-08-04T18:02:07.533213+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-492
    audit_id: audit-19b7fc30a962
    attempt_id: attempt-d9c29717b1ff
    target_state: Archived
    evidence_fingerprint: 1bbaa04aa66ecd8eaf48bb0793839eab1b78230b808d8890804a5605b55507bf
    status: Archived
    audit_ids:
    - audit-19b7fc30a962
    applied: true
    created_at: '2026-08-04T18:02:07.533229+00:00'
    applied_at: '2026-08-04T18:02:17.168968+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-19b7fc30a962
    project_id: proj-14849f1b
    task_id: OOMPAH-492
    target_state: Archived
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1bbaa04aa66ecd8eaf48bb0793839eab1b78230b808d8890804a5605b55507bf
    attempts:
    - version: 1
      attempt_id: attempt-d9c29717b1ff
      target_state: Archived
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 1bbaa04aa66ecd8eaf48bb0793839eab1b78230b808d8890804a5605b55507bf
      created_at: '2026-08-04T17:58:20.397589+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T17:58:20.397589+00:00'
      branch_key: epic-OOMPAH-490
      verdict: pass
      completed_at: '2026-08-04T18:02:07.533035+00:00'
      ended_at: '2026-08-04T18:02:07.533035+00:00'
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T17:25:55.787582+00:00'
    updated_at: '2026-08-04T18:02:07.533035+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d9c29717b1ff
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1bbaa04aa66ecd8eaf48bb0793839eab1b78230b808d8890804a5605b55507bf
    created_at: '2026-08-04T17:58:20.397589+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T17:58:20.397589+00:00'
    branch_key: epic-OOMPAH-490
---
## Summary

Implementation scope

Isolate the known worker-exit and epic-rebase tests that fell through to the checkout's live tracker. In `tests/test_event_driven_loop.py`, give every `RunningEntry.issue` in `TestWorkerExitPostsEvent` a test project ID, inject a `MagicMock` tracker through `_tracker_for_project`, and mock unrelated telemetry/comment/completion side effects so the test exercises only event publication. Combine the normal and abnormal variants only if the assertion remains clear. Apply the same isolation to worker-exit tests in `tests/test_acp_billing.py` that currently spend seconds in unrelated tracker work. In `tests/test_epic_rebase_state.py::TestPersistence::test_persists_on_clear`, pass `project_id="proj-1"` to both set and clear operations so the already-injected project tracker is used. Inspect neighboring tests in these three classes for the same missing-project pattern and correct confirmed cases.

Tests

Add a fail-fast mock in each affected test that raises if `subprocess.run` or `subprocess.Popen` receives a Git push command. Assert the expected tracker interactions as well as the original event, billing, or persistence result. Run the three affected files with `--durations=20`; the two event tests and the clear-persistence test must not spawn Git and should complete without network-scale delays. Then run `make test` after the safety prerequisite is available.

Acceptance criteria

The affected tests cannot reach `orch.tracker` or the checkout's `origin`, retain their original behavioral assertions, leave no background tasks, and no individual case waits on a network timeout or retry path.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 14:56
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-28 14:56
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-28 14:57
---
Understanding: Screening OOMPAH-492 for an existing task covering the same live-tracker/origin leakage in worker-exit, ACP billing, and epic-rebase tests. I will search task history and project decisions, inspect plausible candidates in full, and either archive as a confirmed duplicate or hand off for implementation without changing code.
---
author: oompah
created: 2026-07-28 14:58
---
Discovery: Duplicate screening found no confirmed duplicate. Exact searches across .oompah/tasks, docs, plans, README.md, and WORKFLOW.md found no prior task covering TestWorkerExitPostsEvent/test_acp_billing/test_persists_on_clear live-tracker leakage or the missing project_id pattern. Closest tasks reviewed in full: OOMPAH-491 adds the suite-wide Git transport barrier but explicitly identifies OOMPAH-492 as distinct targeted leak-site isolation; OOMPAH-500 is the downstream clean-checkout/no-network audit; parent OOMPAH-490 assigns this fixture-isolation scope uniquely to OOMPAH-492.
---
author: oompah
created: 2026-07-28 14:58
---
Focus handoff: duplicate_detector

1. Outcome: No confirmed duplicate; OOMPAH-492 should proceed to implementation.
2. Evidence: Searched task records and project docs for the three named test files/classes, worker-exit tests, live tracker access, project_id omissions, Git push guards, isolation, and network delays. Reviewed OOMPAH-491, OOMPAH-500, and parent OOMPAH-490 in full. OOMPAH-491 is the completed suite-wide remote barrier; OOMPAH-500 is the final audit; neither performs these targeted fixture corrections.
3. Remaining work/risks: Update only the affected and confirmed neighboring tests in tests/test_event_driven_loop.py, tests/test_acp_billing.py, and tests/test_epic_rebase_state.py; inject project-scoped mock trackers, isolate unrelated side effects, add fail-fast Git push guards, retain original assertions, run the three files with --durations=20, then make test. Watch for background tasks and any orch.tracker fallback.
4. Recommended next focus: test implementation. No code was changed or tests run during duplicate screening.
---
author: oompah
created: 2026-07-28 14:58
---
Agent completed successfully in 92s (407832 tokens)
---
author: oompah
created: 2026-07-28 14:58
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 14
- Tokens: 404.8K in / 3.0K out [407.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 32s
- Log: OOMPAH-492__20260728T145655Z.jsonl
---
author: oompah
created: 2026-07-28 14:58
---
Focus handoff from `duplicate_detector` is complete. Queued a fresh agent run for the next applicable focus. The next agent should begin with the preceding Focus handoff comment.
---
author: oompah
created: 2026-07-28 14:58
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-28 14:58
---
Focus: Test Engineer
---
author: oompah
created: 2026-07-28 14:58
---
Understanding: As the Test Engineer, I will isolate worker-exit and epic-rebase tests from the live tracker in three files: tests/test_event_driven_loop.py (TestWorkerExitPostsEvent), tests/test_acp_billing.py (worker-exit tests), and tests/test_epic_rebase_state.py (TestPersistence::test_persists_on_clear). Plan: (1) Read all three test files plus relevant source to understand patterns, (2) inject project-scoped mock trackers via _tracker_for_project, (3) add fail-fast git push guards, (4) assert expected tracker interactions, (5) run the three files with --durations=20, then make test.
---
author: oompah
created: 2026-07-28 15:07
---
Discovery: Root causes identified in three test files:\n\n1. tests/test_event_driven_loop.py::TestWorkerExitPostsEvent: Issue objects created without project_id, causing _on_worker_exit to fall back to self.tracker (live). No mocks for _fire_task_cost_record, _fire_telemetry_comment, _post_comment, or completion gates (_run_close_gate, _ensure_review_exists). Fix: add project_id='proj-test' to Issue, inject mock tracker via _tracker_for_project, mock side-effects, set close_gate_enabled=False.\n\n2. tests/test_acp_billing.py::TestOnWorkerExitCostAccumulation (3 tests) + TestMissingRatesWarningLogged::test_on_worker_exit_no_cost_no_crash: Same pattern - _make_issue() creates Issue with no project_id. Fix: add project_id='proj-test' to _make_issue(), add close_gate_enabled=False to _make_orchestrator(), inject mock tracker and side-effect mocks per test.\n\n3. tests/test_epic_rebase_state.py::TestPersistence::test_persists_on_clear: _set_epic_rebase_state and _clear_epic_rebase_state both called without project_id even though _tracker_for_project is already mocked. Fix: pass project_id='proj-1' to both calls.\n\nAll fixes will add fail-fast subprocess git-push guards and assert tracker was called via project_id.
---
author: oompah
created: 2026-07-28 15:18
---
Implementation: Applied isolation fixes to three test files.\n\n1. tests/test_event_driven_loop.py::TestWorkerExitPostsEvent:\n   - Added project_id='proj-test' to Issue in _make_running_entry()\n   - Added _inject_isolation_mocks() that wires _tracker_for_project to a MagicMock (terminal 'Done' issue), silences fire-and-forget telemetry, comment posting, completion gates, and retry scheduling\n   - Added _fail_on_git_push() fail-fast guard (raises on git push)\n   - Used close_gate_enabled=False to skip git-touching gate checks\n   - Both test methods now assert _tracker_for_project was called with 'proj-test'\n\n2. tests/test_acp_billing.py (TestOnWorkerExitCostAccumulation + TestMissingRatesWarningLogged::test_on_worker_exit_no_cost_no_crash):\n   - Added project_id param to _make_issue() (default None preserves backward compat)\n   - Added close_gate_enabled=False to _make_orchestrator() config\n   - Added module-level _inject_worker_exit_isolation() and _no_git_push() helpers\n   - Configured project_store.get.return_value=None to prevent MagicMock attributes looking like a 'paused' project\n   - 4 tests now use project_id='proj-test' + isolation + subprocess guards\n\n3. tests/test_epic_rebase_state.py::TestPersistence::test_persists_on_clear:\n   - Pass project_id='proj-1' to both _set_epic_rebase_state and _clear_epic_rebase_state\n   - Added subprocess guard\n   - Assert _tracker_for_project was called with 'proj-1'
---
author: oompah
created: 2026-07-28 15:18
---
Verification: All tests pass.\n\n- tests/test_event_driven_loop.py::TestWorkerExitPostsEvent: 2 passed (no git spawned, < 0.005s each)\n- tests/test_acp_billing.py::TestOnWorkerExitCostAccumulation: 3 passed\n- tests/test_acp_billing.py::TestMissingRatesWarningLogged::test_on_worker_exit_no_cost_no_crash: passed\n- tests/test_epic_rebase_state.py::TestPersistence::test_persists_on_clear: passed\n\nFull suite: make test -> 12361 passed, 7 skipped, 0 failures (264s)\n\nThe 2 TestFullSyncIntervalConfig failures seen when running the event-driven file in isolation are pre-existing bugs (verified by git stash + re-run); they were already failing before this PR and are not within OOMPAH-492 scope.\n\nAll affected tests: cannot reach orch.tracker or git origin, retain original behavioral assertions, leave no background tasks, complete without network-scale delays.
---
author: oompah
created: 2026-07-28 15:18
---
Completion: Delivered isolation fixes for all identified live-tracker leak sites.\n\nFiles changed:\n- tests/test_event_driven_loop.py: TestWorkerExitPostsEvent now injects project-scoped mock tracker, silences all unrelated side-effects (telemetry, comments, completion gates, retry scheduling), and adds fail-fast git-push guard.\n- tests/test_acp_billing.py: Module-level helpers _inject_worker_exit_isolation() and _no_git_push() isolate 4 worker-exit tests. Added project_id param to _make_issue(), close_gate_enabled=False to _make_orchestrator().\n- tests/test_epic_rebase_state.py: test_persists_on_clear now passes project_id='proj-1' to both state operations so the already-mocked tracker is used.\n\nAll acceptance criteria satisfied: no live tracker access, no git origin reachability, original assertions preserved, no background task leakage, no network-scale delays.
---
author: oompah
created: 2026-07-28 15:18
---
Isolated worker-exit and epic-rebase tests from live tracker. Added project IDs, injected MagicMock trackers via _tracker_for_project, muted fire-and-forget telemetry/comment/completion side-effects, added fail-fast git-push subprocess guards, and asserted project-scoped tracker usage. All 3 files affected, 7 tests isolated, make test passes (12361/0 fail).
---
author: oompah
created: 2026-07-28 15:18
---
Agent completed successfully in 1217s (51504 tokens)
---
author: oompah
created: 2026-07-28 15:18
---
Run #1 [attempt=1, profile=deep, role=deep -> Claude/default]
- Turns: 166, Tool calls: 99
- Tokens: 89 in / 51.4K out [51.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 20m 17s
- Log: OOMPAH-492__20260728T145838Z.jsonl
---
author: oompah
created: 2026-08-04 17:26
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-04 17:58
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-04 17:58
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-04 18:02
---
Audit PASS — Archived

[REDACTED]

Safe evidence:
- implementation_commit: e8e03d7d1d6c4cdfa2bd047bb538c784dfcb2a87
- commit_title: OOMPAH-492: Isolate worker-exit and epic-rebase tests from live tracker
- origin_main_head: a681ec2fc005f339063b3b8e2a139b8ae0b3c379
- commit_on_origin_main: true
- files_changed: tests/test_acp_billing.py, tests/test_epic_rebase_state.py, tests/test_event_driven_loop.py
- diff_summary: 187 insertions, 22 deletions across 3 files
- isolation_patterns_present: _inject_isolation_mocks, _inject_worker_exit_isolation, _fail_on_git_push, _no_git_push, project_id=proj-1 in test_persists_on_clear
- auto_archive_reason: Aged Merged auto-archive (closed 7 days ago)
---
author: oompah
created: 2026-08-04 18:02
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 33, Tool calls: 24
- Tokens: 25 in / 5.4K out [5.5K total]
- Cost: $0.0000
- Exit: normal, Duration: 4m 3s
- Log: OOMPAH-492__20260804T175846Z.jsonl
---
<!-- COMMENTS:END -->
