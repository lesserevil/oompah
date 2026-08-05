---
id: OOMPAH-814
type: task
status: Ready to Integrate
priority: null
title: Make submit-queue dispatch fixtures deterministic under full-gate load
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-04T23:55:41.082395Z'
updated_at: '2026-08-05T01:25:49.442130Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-814
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-814
  base_branch: epic-OOMPAH-763
  base_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
  head_sha: 254b131c713bece56500a72408f796c46bfee8d0
  submitted_at: '2026-08-05T01:25:39.762537+00:00'
  updated_at: '2026-08-05T01:25:39.762537+00:00'
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-814
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 52db7c21f436ded1c4c3012e9d528c9a03d71c4ce544a8776a2e04fe1449e147
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-05T00:30:51.883100+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest active tasks OOMPAH-807 and OOMPAH-815 address\
    \ revisionless audits and accepted-branch identity; neither concerns deterministic\
    \ submit-queue test fixtures or mock/tracker resource cleanup.\nFocus handoff:\
    \ duplicate_detector  \nDuplicate preflight verdict: no_duplicate  \nMatches:\
    \ none  \n\nEvidence: Closest active tasks OOMPAH-807 and OOMPAH-815 address revisionless\
    \ audits and accepted-branch identity; neither concerns deterministic submit-queue\
    \ test fixtures or mock/tracker resource cleanup."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.task_costs:
  total_input_tokens: 50860
  total_output_tokens: 306
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50860
      output_tokens: 306
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50860
    output_tokens: 306
    cost_usd: 0.0
    recorded_at: '2026-08-05T00:30:51.870607+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-814__20260805T003011Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: epic-OOMPAH-763--task-OOMPAH-814
    source_sha: cb1446d4beba7ad83a1b67d94574ad5c01cf8814
    completed_at: '2026-08-05T00:30:51.940545+00:00'
---
## Summary

Exact full-gate reproduction on OOMPAH-807 at 069633eeb: 15,709 tests passed, but tests/test_submit_queue_concurrency.py::TestShouldDispatchOpenReviewGate::test_cap3_two_open_dispatches exceeded the global five-second timeout while unittest.mock dynamically created an unset Project.default_branch child inside Orchestrator._new_tracker_for_project. Isolated exact test, full module serial/xdist, and 40 concurrent process repetitions pass, proving a load-sensitive incomplete fixture rather than the asserted review-cap behavior. Implementation scope: make the test project/tracker fixture concrete and complete for every attribute the dispatch path reads, avoid dynamic MagicMock child creation and accidental real tracker construction, and close any orchestrator-owned resources. Audit neighboring submit-queue fixtures for the same incomplete project double without weakening dispatch assertions or increasing the global timeout. Required tests: exact test repeated under parallel load, complete test_submit_queue_concurrency serial and xdist, relevant dispatch/tracker factory tests, terminal mutation scan, and exact server full gate. Acceptance: review-cap assertions exercise only dispatch policy, never instantiate a real tracker or synthesize mock attributes, and stay below the lifecycle timeout under full-suite load.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 23:56
---
Claimed implementation in /home/shedwards/.oompah/worktrees/oompah/OOMPAH-814 on epic-OOMPAH-763--task-OOMPAH-814 at exact parent 30dc2b2075a48c6c542da55a46ad0285f492d527. Reproducing the submit-queue fixture path and auditing neighboring project/tracker doubles before a tests-only patch; submission and owner-claim release remain with the landing coordinator.
---
author: oompah
created: 2026-08-05 00:03
---
Implemented deterministic submit-queue fixtures: real Project and ProjectStore objects replace incomplete MagicMock project/store doubles, Orchestrator construction is bounded by concrete no-I/O tracker instances, and every helper-owned executor/store plus the API TestClient is closed. Added regression proving an unset default_branch cannot invoke _new_tracker_for_project during _should_dispatch. Checks passed: exact regression + original failure (2), full module serial (62), full module xdist -n4 (62), 40 repetitions in 8 concurrent processes, related tracker factory tests (12), and make terminal-audit-scan. Preparing the commit/push; exact server full gate and task submission remain with the landing coordinator.
---
author: oompah
created: 2026-08-05 00:04
---
Implementation handoff is pushed at cb1446d4beba7ad83a1b67d94574ad5c01cf8814 on epic-OOMPAH-763--task-OOMPAH-814 (exact base 30dc2b2075a48c6c542da55a46ad0285f492d527). Branch is clean and up to date with origin. Focused verification remains green: module serial 62/62, module xdist -n4 62/62, related tracker factory tests 12/12, 40 concurrent repetitions, terminal mutation scan. Per coordination instructions, I did not submit OOMPAH-814 or release its owner claim; landing coordinator should land this ahead of rebasing OOMPAH-807 and run the exact server full gate.
---
author: oompah
created: 2026-08-05 00:05
---
Made submit-queue dispatch fixtures deterministic under full-gate load at cb1446d4beba7ad83a1b67d94574ad5c01cf8814. Concrete project/store/tracker boundaries avoid dynamic MagicMock tracker construction and helper resources are closed. Exact+regression 2/2, module serial/xdist 62/62, 40 repetitions at concurrency 8, tracker factory 12/12, terminal scan pass.
---
author: oompah
created: 2026-08-05 00:23
---
The combined-tree quality gate failed on `OOMPAH-814`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
waited
    async for msg in client.receive_response():
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_server_release_picks.py::TestPatchReleasePicksEndpoint::test_returns_400_on_invalid_json
tests/test_server_release_picks.py::TestPostApplyReleasePicksToAllChildren::test_returns_400_on_invalid_json
  /home/shedwards/.oompah/tmp/oompah-quality-gate-6afipm7k/workspace/.venv/lib/python3.12/site-packages/httpx/_models.py:408: DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.
    headers, stream = encode_request(

tests/test_submission_fencing.py::test_clean_submission_with_no_late_changes_proceeds_to_integration
tests/test_submission_fencing.py::test_late_tracked_changes_after_submission_acceptance_are_detected
  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/events.py:88: RuntimeWarning: coroutine 'sleep' was never awaited
    self._context.run(self._callback, *self._args)
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_submit_queue_concurrency.py::TestServerMaxInFlightPrsAPI::test_list_projects_includes_max_in_flight_prs
  /home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/coroutines.py:13: RuntimeWarning: coroutine 'sleep' was never awaited
    bool(os.environ.get('PYTHONASYNCIODEBUG')))
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_webhooks.py::TestForwarderProcessFullLifecycle::test_polling_resume_when_forwarder_process_dies
tests/test_websocket_authenticated_bootstrap.py::TestWebSocketBootstrapIncludesAuth::test_ws_bootstrap_includes_api_metrics
  /home/shedwards/.oompah/tmp/oompah-quality-gate-6afipm7k/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7a78c37979c0>
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
      self.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_orchestrator_merged.py::TestShouldDispatchCompleted::test_short_description_accepted
= 1 failed, 15694 passed, 8 skipped, 1 xfailed, 48 warnings in 826.72s (0:13:46) =

make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-05 00:26
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-05 00:26
---
Agent failed: Task worktree /home/shedwards/.oompah/worktrees/oompah/OOMPAH-814 is on OOMPAH-814, not expected branch epic-OOMPAH-763--task-OOMPAH-814; refusing to reset it. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-05 00:26
---
Run #1 [attempt=1, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 14s
---
author: oompah
created: 2026-08-05 00:27
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 00:28
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 28s
---
author: oompah
created: 2026-08-05 00:29
---
Exact second-gate diagnosis: TestShouldDispatchCompleted._make_orchestrator creates a real OompahMarkdownTracker; all five cases reach _issue_has_children and scan ~282 native task files, while the fixture leaks two pools and five durable stores. Under full-gate load short_description exceeded 5s. Minimal fix: concrete tmp ProjectStore + no-I/O fetch_children tracker boundary, explicit executor/store cleanup, and assertion no real tracker factory runs. Same audit found TestDispatchSerializationByProject dynamically creates a fake Project and caches a real tracker under a MagicMock key; TestBudgetGateFreeTierBypass also uses a real legacy tracker and incompletely closes stores. Fix these direct-dispatch neighboring fixtures within this task, without raising timeouts; read-only diagnosis made no code changes.
---
author: oompah
created: 2026-08-05 00:29
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 00:29
---
In-flight workaround for OOMPAH-815: preserved exact accepted head cb1446d4beba7ad83a1b67d94574ad5c01cf8814 by creating/pushing the server-derived branch epic-OOMPAH-763--task-OOMPAH-814 at the identical commit and switching the clean registered worktree to it. No reset, rewrite, code change, or deletion occurred; origin/OOMPAH-814 remains as recovery evidence. Task is Open and unclaimed so the server can retry implementation on the now-matching branch. OOMPAH-815 tracks the systemic accepted-branch identity defect.
---
author: oompah
created: 2026-08-05 00:29
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-05 00:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.9K in / 306 out [51.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 11s
- Log: OOMPAH-814__20260805T003011Z.jsonl
---
author: oompah
created: 2026-08-05 00:31
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-05 00:31
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-05 00:37
---
UNDERSTANDING: The quality gate failed on test_orchestrator_merged.py::TestShouldDispatchCompleted::test_short_description_accepted which exceeded the 5s timeout under full-gate load. Root cause (from diagnosis): TestShouldDispatchCompleted._make_orchestrator creates a real OompahMarkdownTracker that scans ~282 native task files, leaking two pools and five durable stores. Plan: (1) Replace incomplete fixtures in TestShouldDispatchCompleted, TestDispatchSerializationByProject, and TestBudgetGateFreeTierBypass with concrete ProjectStore and no-I/O _DispatchTracker similar to the submit_queue_concurrency changes; (2) Add explicit cleanup for orchestrator resources; (3) Verify all tests pass both in isolation and under full-gate load.
---
author: oompah
created: 2026-08-05 00:38
---
Systemic concurrent-load evidence filed as OOMPAH-816: during OOMPAH-813's exact four-worker gate, the OOMPAH-508 completion auditor launched a second full serial suite; both trees entered filesystem journal waits. Continue this task's concrete fixture isolation/cleanup, but if the new exact gate loses another unrelated test under concurrent full-suite load, classify that as OOMPAH-816 validation-resource arbitration rather than weakening assertions or increasing global timeouts.
---
author: oompah
created: 2026-08-05 00:50
---
Acceptance blocker in the current live diff: TestDispatchSerializationByProject still passes projects=None with a MagicMock store. issue.project_id='proj-1'; store.get returns None, then unset MagicMock.find_by_name dynamically returns a fake Project and _tracker_for_project can still construct/cache a real OompahMarkdownTracker. Patching only Orchestrator._new_tracker covers the legacy tracker, not _new_tracker_for_project. The 5-case class taking 7.58s is consistent with remaining real I/O. Replace this with a concrete tmp ProjectStore containing a concrete Project and preseed/constrain the exact project tracker boundary; add an assertion/raising spy proving _new_tracker_for_project is never invoked. Do the same concrete empty-store boundary for TestShouldDispatchCompleted, and remove currently unused Project/ProjectStore imports only if not used. Keep explicit cleanup. Do not submit based only on focused pass while the accidental real tracker path remains.
---
author: oompah
created: 2026-08-05 00:59
---
Oompah could not durably preserve this worker's task worktree before retry. The worktree was left in place and no reset, clean, or retry was started. Reconcile the workspace and recovery evidence manually before resuming the task. Error: could not persist recovery ref for OOMPAH-814: fatal: update_ref failed for ref 'refs/oompah/recovery/OOMPAH-814-2d1c3b305041c4f0': cannot update ref 'refs/oompah/recovery/OOMPAH-814-2d1c3b305041c4f0': trying to write ref 'refs/oompah/recovery/OOMPAH-814-2d1c3b305041c4f0' with nonexistent object 515cbc2c84ef6bf955468534a163b7fc77b33f2a
---
author: oompah
created: 2026-08-05 01:03
---
Direct-owner repair completed at local exact head 11d5b97d69f4d521243f8d98a2c7c31439b60f1c after the server worker failed to consume its acceptance blocker. TestShouldDispatchCompleted now uses a concrete empty temporary ProjectStore; TestDispatchSerializationByProject uses a complete concrete proj-1 Project plus preseeded no-I/O tracker; all three repaired fixture families install a raising _new_tracker_for_project spy. The combined test_orchestrator_merged + submit_queue_concurrency suite improved from 227 tests in roughly 140s to 227 passed in 2.31s, with the affected 15 tests in 0.54s. Terminal mutation scan 8/8, F401, and diff check pass. Awaiting independent exact-diff review before push/submission.
---
author: oompah
created: 2026-08-05 01:06
---
Removed accidental real project-tracker I/O from three dispatch-policy fixture families using concrete temporary stores/projects, preseeded no-I/O trackers, raising factory guards, and complete resource cleanup. Exact head 254b131c7; 227 related tests pass in 2.31s and independent review accepted.
---
author: oompah
created: 2026-08-05 01:21
---
The combined-tree quality gate failed on `epic-OOMPAH-763--task-OOMPAH-814`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
TestForwarderProcessFullLifecycle::test_stop_terminates_all_tracked_processes
  /home/shedwards/.oompah/tmp/oompah-quality-gate-r0e807m_/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7f930d20b9c0>
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
      self.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

tests/test_websocket_authenticated_bootstrap.py::TestWebSocketRefreshIncludesAuth::test_ws_refresh_includes_http_auth
  /home/shedwards/.oompah/tmp/oompah-quality-gate-r0e807m_/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7a49bf8979c0>
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
      self.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_event_driven_loop.py::TestRetryTimerResetsInProgressOnRelease::test_does_not_reset_when_running_agent_exists
FAILED tests/test_release_delivery_refresh.py::TestTrickleScaleBacklogRegressionOOMPAH251::test_scm_calls_bounded_by_items_with_deleted_branches
= 2 failed, 15693 passed, 8 skipped, 1 xfailed, 45 warnings in 785.45s (0:13:05) =

make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-05 01:21
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #22)

**State audited:** `Needs CI Fix`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** current CI evidence is passing; safe to reopen the stalled task.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-08-05 01:25
---
In-flight workaround after OOMPAH-818 watchdog misclassification: reclaimed exact clean head 254b131c713bece56500a72408f796c46bfee8d0. The two unrelated full-gate failures both pass in isolation and across 20/20 sequential repetitions (40 focused executions total); this task's repaired 227-test fixture matrix remains green and no code changed after the accepted review. Resubmitting the identical exact head for an authoritative gate while OOMPAH-816 implements host-wide heavyweight-command arbitration. OOMPAH-807 stays blocked until a successful exact gate.
---
author: oompah
created: 2026-08-05 01:25
---
Resubmitted unchanged exact head 254b131c7 after fresh 20/20 isolated repetitions of the two unrelated load-sensitive failures; fixture repair remains independently accepted.
---
<!-- COMMENTS:END -->
