---
id: OOMPAH-765
type: epic
status: In Review
priority: 1
title: Build unified versioned facts and a pure WorkDecision evaluator
parent: OOMPAH-763
children:
- OOMPAH-777
- OOMPAH-779
- OOMPAH-786
blocked_by: []
start_blocked_by: &id001
- OOMPAH-764
labels:
- ci-fix
- needs-rebase
assignee: null
created_at: '2026-08-04T13:55:54.087142Z'
updated_at: '2026-08-04T16:58:23.024933Z'
work_branch: epic-OOMPAH-765
target_branch: epic-OOMPAH-763
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.target_branch: epic-OOMPAH-763
oompah.work_branch: epic-OOMPAH-765
oompah.agent_run_id: c97e7a73-ec45-4bc1-a474-7d01f357dcc7
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: epic-OOMPAH-765
  base_branch: epic-OOMPAH-763
  head_sha: c7bfbcc3b638b3ea28d241852af6345164ba86f6
  submitted_at: '2026-08-04T16:43:17.687981+00:00'
  updated_at: '2026-08-04T16:44:27.962400+00:00'
  last_error: 'could not recover integration worktrees: git worktree add failed: Preparing
    worktree (checking out ''epic-OOMPAH-765'')

    fatal: ''epic-OOMPAH-765'' is already used by worktree at ''/home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-765'''
oompah.task_costs:
  total_input_tokens: 83
  total_output_tokens: 22845
  total_cost_usd: 0.0
  by_model:
    opus:
      input_tokens: 83
      output_tokens: 22845
      cost_usd: 0.0
  runs:
  - profile: deep
    model: opus
    input_tokens: 83
    output_tokens: 22845
    cost_usd: 0.0
    recorded_at: '2026-08-04T16:43:42.184185+00:00'
---
## Summary

Create versioned WorkflowFacts and a pure evaluate_task(task, facts) -> WorkDecision engine. Facts must normalize tracker state, dependencies, containment, integration records/queue rows, terminal audit records, review/CI state, Git/forge landing evidence, ownership generations, retry budgets, and configuration. WorkDecision must be total for every task and return disposition (runnable, owned, blocked, retry_scheduled, action_required, terminal), stable reason code, responsible owner type, unmet prerequisites, evidence revision, next reassessment time, permitted actions, action_required flag, and alert level. Centralize dependency satisfaction, target/landing resolution, and retry classification. Run shadow evaluation without mutations, compare with legacy scheduler/UI/watchdog decisions, and expose a diagnostic API. Required tests: pure table-driven decisions, deterministic evidence revisions, multi-project scope, missing/stale/error facts, nested epic landing, cross-epic dependencies, and shadow disagreement telemetry. Acceptance: every nonterminal task produces a deterministic decision; scheduler, UI, and liveness consumers can use the same object; unexplained shadow divergences are zero before enforcement.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 16:18
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-765`
Target: `epic-OOMPAH-763`
Head: `40e46bf8e41c15a0a89529694cbb3aa3580f2f19`
Command: `make test`
Result: `failed`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
hon-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/selector_events.py", line 282, in _add_reader
      key = self._selector.get_key(fd)
            ^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/selectors.py", line 192, in get_key
      raise KeyError("{!r} is not registered".format(fileobj)) from None
  KeyError: '114 is not registered'
  
  During handling of the above exception, another exception occurred:
  
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

tests/test_websocket_authenticated_bootstrap.py::TestWebSocketBootstrapIncludesAuth::test_ws_bootstrap_includes_api_metrics
  /home/shedwards/.oompah/tmp/oompah-quality-gate-i9ijw8v0/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7131f66b39c0>
  
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
FAILED tests/test_orchestrator_handlers.py::TestRunStep5cEpicMaintenance::test_tick_does_not_await_epic_maintenance
= 1 failed, 15549 passed, 8 skipped, 1 xfailed, 48 warnings in 420.08s (0:07:00) =

make: *** [Makefile:401: test] Error 1
```
---
author: oompah
created: 2026-08-04 16:23
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-04 16:23
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-08-04 16:27
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-765`
Target: `epic-OOMPAH-763`
Head: `40e46bf8e41c15a0a89529694cbb3aa3580f2f19`
Command: `make test`
Result: `needs_rebase`

Required: rebase this branch onto the current deployed base so it contains the lifecycle safety prerequisite and does not replace the protected gate entrypoints. Run the full command, commit and push the repair, then leave the task in Done; Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
The quality-gate worktree has uncommitted changes. Commit and push the repair before rerunning the exact review-head gate.
```
---
author: oompah
created: 2026-08-04 16:30
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-765`
Target: `epic-OOMPAH-763`
Head: `40e46bf8e41c15a0a89529694cbb3aa3580f2f19`
Command: `make test`
Result: `needs_rebase`

Required: rebase this branch onto the current deployed base so it contains the lifecycle safety prerequisite and does not replace the protected gate entrypoints. Run the full command, commit and push the repair, then leave the task in Done; Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
The quality-gate worktree has uncommitted changes. Commit and push the repair before rerunning the exact review-head gate.
```
---
author: oompah
created: 2026-08-04 16:31
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-765`
Target: `epic-OOMPAH-763`
Head: `40e46bf8e41c15a0a89529694cbb3aa3580f2f19`
Command: `make test`
Result: `needs_rebase`

Required: rebase this branch onto the current deployed base so it contains the lifecycle safety prerequisite and does not replace the protected gate entrypoints. Run the full command, commit and push the repair, then leave the task in Done; Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
The quality-gate worktree has uncommitted changes. Commit and push the repair before rerunning the exact review-head gate.
```
---
author: oompah
created: 2026-08-04 16:32
---
[watchdog:stalled_task] Stalled-task watchdog audit (run #21)

**State audited:** `Needs Rebase`
**Classification:** `actionable`
**Action:** `reopen`
**Evidence:** current SCM evidence shows the stalled branch/rebase condition is resolved.

*This comment is posted automatically by the oompah stalled-task watchdog. No human action required unless the classification above is incorrect.*
---
author: oompah
created: 2026-08-04 16:33
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-765`
Target: `epic-OOMPAH-763`
Head: `40e46bf8e41c15a0a89529694cbb3aa3580f2f19`
Command: `make test`
Result: `needs_rebase`

Required: rebase this branch onto the current deployed base so it contains the lifecycle safety prerequisite and does not replace the protected gate entrypoints. Run the full command, commit and push the repair, then leave the task in Done; Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
The quality-gate worktree has uncommitted changes. Commit and push the repair before rerunning the exact review-head gate.
```
---
author: oompah
created: 2026-08-04 16:37
---
Branch quality gate blocked review creation.

Branch: `epic-OOMPAH-765`
Target: `epic-OOMPAH-763`
Head: `40e46bf8e41c15a0a89529694cbb3aa3580f2f19`
Command: `make test`
Result: `needs_rebase`

Required: rebase this branch onto the current deployed base so it contains the lifecycle safety prerequisite and does not replace the protected gate entrypoints. Run the full command, commit and push the repair, then leave the task in Done; Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
The quality-gate worktree has uncommitted changes. Commit and push the repair before rerunning the exact review-head gate.
```
---
author: oompah
created: 2026-08-04 16:39
---
Understanding: The CI failure is a flaky assertion in test_tick_does_not_await_epic_maintenance. Root cause: _handle_dispatch_needed is mocked as bare AsyncMock() which returns an AsyncMock instance whose .items() call yields a coroutine. When tick's total_ms > 2000ms under CI parallel load, _tick() executes _dispatch_detail = ' '.join(f'{k}={v:.0f}' for k, v in dispatch_timings.items()). Iterating the coroutine raises TypeError, propagating out of await orch._tick() and failing the test. The sibling test test_tick_sets_epic_maintenance_future already fixed this by using AsyncMock(return_value={}) and documents the exact contract. Plan: apply the same minimal fix to test_tick_does_not_await_epic_maintenance.
---
author: oompah
created: 2026-08-04 16:41
---
Discovery + Implementation: Confirmed root cause. AsyncMock() returns an AsyncMock instance whose child attribute .items() is a coroutine, not an iterable. When _tick() total_ms > 2000 (easily reached under CI parallel load in a quality-gate sandbox), the slow-tick diagnostic code path 'for k, v in dispatch_timings.items()' raises TypeError: 'coroutine' object is not iterable, which propagates out of await orch._tick() and fails the assertion. Fix: mirror the sibling test test_tick_sets_epic_maintenance_future by using AsyncMock(return_value={}) with the same explanatory comment. Verified: 14/14 TestRunStep5cEpicMaintenance tests pass; 279/279 test_orchestrator_handlers.py tests pass with parallel workers.
---
author: oompah
created: 2026-08-04 16:42
---
Verification + Completion: Fix committed as c7bfbcc3b and pushed to epic-OOMPAH-765. Verified locally: TestRunStep5cEpicMaintenance (14/14) and full test_orchestrator_handlers.py suite (279/279) pass with parallel workers under 5s timeout. Minimal one-line change; no production code touched. Ready for the branch quality gate to rerun make test.
---
author: oompah
created: 2026-08-04 16:43
---
Fixed slow-tick AsyncMock coroutine iteration in test_tick_does_not_await_epic_maintenance by mirroring the sibling test's return_value={} pattern. 14/14 epic maintenance tests and 279/279 orchestrator handler tests pass locally with parallel workers.
---
author: oompah
created: 2026-08-04 16:43
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/opus]
- Turns: 0, Tool calls: 77
- Tokens: 83 in / 22.8K out [22.9K total]
- Cost: $0.0000
- Exit: terminated, Duration: 20m 17s
- Log: OOMPAH-765__20260804T162335Z.jsonl
---
author: oompah
created: 2026-08-04 16:44
---
Integration could not verify `epic-OOMPAH-765`: could not recover integration worktrees: git worktree add failed: Preparing worktree (checking out 'epic-OOMPAH-765')
fatal: 'epic-OOMPAH-765' is already used by worktree at '/home/shedwards/.oompah/worktrees/oompah/epic-OOMPAH-765'

Fetch the private branch, preserve its commits, push a clean current head, and submit it again.
---
author: oompah
created: 2026-08-04 16:58
---
Branch quality gate passed for `c7bfbcc3b638b3ea28d241852af6345164ba86f6` using `make test` in 428.7s. Review creation may proceed.
---
<!-- COMMENTS:END -->
