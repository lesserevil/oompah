---
id: OOMPAH-814
type: task
status: Open
priority: null
title: Make submit-queue dispatch fixtures deterministic under full-gate load
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T23:55:41.082395Z'
updated_at: '2026-08-05T00:26:49.503801Z'
work_branch: epic-OOMPAH-763--task-OOMPAH-814
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-763--task-OOMPAH-814
  base_branch: epic-OOMPAH-763
  base_sha: 30dc2b2075a48c6c542da55a46ad0285f492d527
  updated_at: '2026-08-05T00:26:09.312481+00:00'
oompah.agent_run_id: f2fb949e-5b8b-4c02-b32d-2ada5f975cf6
oompah.work_branch: epic-OOMPAH-763--task-OOMPAH-814
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
<!-- COMMENTS:END -->
