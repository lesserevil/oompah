---
id: OOMPAH-837
type: task
status: Needs CI Fix
priority: 1
title: Bind epic rollup, delivery, repair, and cleanup to durable handlers
parent: OOMPAH-804
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:45.984953Z'
updated_at: '2026-08-06T11:47:55.595448Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: blocked
  attempts: 1
  task_branch: OOMPAH-837
  base_branch: epic-OOMPAH-804
  base_sha: c31b8d32aeeee2fe4de82c9b51614a84f5937770
  head_sha: c31b8d32aeeee2fe4de82c9b51614a84f5937770
  submitted_at: '2026-08-06T10:06:40.718937+00:00'
  updated_at: '2026-08-06T11:47:48.130992+00:00'
  last_error: "Combined-tree quality gate failed:  \n  Traceback (most recent call\
    \ last):\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/unittest/mock.py\"\
    , line 1427, in get_original\n      original = target.__dict__[name]\n       \
    \          ~~~~~~~~~~~~~~~^^^^^^\n  KeyError: '_terminate'\n  \n  During handling\
    \ of the above exception, another exception occurred:\n  \n  Traceback (most recent\
    \ call last):\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 126, in __del__\n      self.close()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 104, in close\n      proto.pipe.close()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 568, in close\n      self._close(None)\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 592, in _close\n      self._loop.call_soon(self._call_connection_lost,\
    \ exc)\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 799, in call_soon\n      self._check_closed()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 545, in _check_closed\n      raise RuntimeError('Event loop is closed')\n\
    \  RuntimeError: Event loop is closed\n  \n  Enable tracemalloc to get traceback\
    \ where the object was allocated.\n  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))\n\
    \n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n===========================\
    \ short test summary info ============================\nFAILED tests/test_epic_rebase_state.py::TestEpicTargetResolution::test_wrong_target_helper_is_archived_without_recovery_ref_cleanup\n\
    = 1 failed, 16631 passed, 8 skipped, 1 xfailed, 46 warnings in 921.06s (0:15:21)\
    \ =\n\n/home/shedwards/.oompah/tmp/oompah-quality-gate-mla42jef/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:33:\
    \ RuntimeWarning: coroutine 'sleep' was never awaited\n  gc.collect()\nRuntimeWarning:\
    \ Enable tracemalloc to get the object allocation traceback\n/home/shedwards/.oompah/tmp/oompah-quality-gate-mla42jef/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67:\
    \ PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__\
    \ at 0x7e429760b9c0>\n\nTraceback (most recent call last):\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 126, in __del__\n    self.close()\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 104, in close\n    proto.pipe.close()\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 568, in close\n    self._close(None)\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 592, in _close\n    self._loop.call_soon(self._call_connection_lost, exc)\n\
    \  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 799, in call_soon\n    self._check_closed()\n  File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 545, in _check_closed\n    raise RuntimeError('Event loop is closed')\n\
    RuntimeError: Event loop is closed\n\nEnable tracemalloc to get traceback where\
    \ the object was allocated.\nSee https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n  warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))\n\
    make: *** [Makefile:401: test] Error 1\n"
---
## Summary

Add EpicWorkflowBackend/EpicWorkflowHandler production contracts and handlers for all ten actions: readiness, rollup reconciliation, child landing verification, rollup review creation, target resolution, auto close, terminal validation, rebase repair, cleanup, and restart reconciliation. Use fresh EpicFactCollector containment/LandingFacts, persist evidence only in enforce mode, build terminal TaskTransitionService intents, and extract exact one-epic review creation, rebase helper, and cleanup bodies from legacy sweeps. Wire production schedule_action wakes for parent/child/target changes, restart, rebase requests, and terminal cleanup. Relevant files: oompah/epic_workflow.py, oompah/workflow_runtime.py or typed adapter modules, orchestrator epic rollup/open-review/rebase/cleanup paths. Required tests: nested epics, immediate-parent targets, child arrival permutations, stale landing evidence, exact review/head CAS, restart after effect before verify, rebase helper idempotency, terminal cleanup evidence, multi-project routing, and shadow zero-write/enforce single-writer behavior. Acceptance: every epic action has a real project-bound handler/event source; no parent-child proof cycle or legacy rollup writer remains active in enforce mode; effects are exactly replayable after restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 19:59
---
Post-review repairs complete. Cleanup now locks/revalidates epic authority before every child deletion, requires terminal lifecycle plus exact own landing for Merged epics (including remote-only top-level branches), and verifies exact remote generations before CAS deletion. Shielded external mutations are included in runtime drain; runtime/store closure fails closed while operations remain. Real Orchestrator staged composition now proves enforce mode refuses partial sibling coverage instead of relying on fakes. The first focused run exposed four test/fixture integration issues; repaired terminal fixture authority, atomic remote-delete expectation, handler-drain scheduling, and exact revalidation evidence. Final focused gate passed: terminal mutation scan green and 419/419 epic adapter/controller, project cleanup, transition service, runtime, rebase-state, and webhook tests passed in 67.78s. Awaiting one fresh independent final review before commit.
---
author: oompah
created: 2026-08-06 09:39
---
Epic rollup/delivery/repair handlers and regression coverage are complete, with exact commit cea87246 included in canonical validated composition f89c477d. Resubmitting canonical head after OOMPAH-858 task-scoped nested-delivery recovery so gate, integration, and audit share one exact candidate.
---
author: oompah
created: 2026-08-06 10:06
---
Shared exact-gate regression repair propagated to canonical head c31b8d32a; 81 formerly failing module tests pass and independent review accepted.
---
author: oompah
created: 2026-08-06 11:47
---
The combined-tree quality gate failed on `OOMPAH-837`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
 
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/unittest/mock.py", line 1427, in get_original
      original = target.__dict__[name]
                 ~~~~~~~~~~~~~~~^^^^^^
  KeyError: '_terminate'
  
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

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_epic_rebase_state.py::TestEpicTargetResolution::test_wrong_target_helper_is_archived_without_recovery_ref_cleanup
= 1 failed, 16631 passed, 8 skipped, 1 xfailed, 46 warnings in 921.06s (0:15:21) =

/home/shedwards/.oompah/tmp/oompah-quality-gate-mla42jef/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:33: RuntimeWarning: coroutine 'sleep' was never awaited
  gc.collect()
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
/home/shedwards/.oompah/tmp/oompah-quality-gate-mla42jef/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7e429760b9c0>

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
make: *** [Makefile:401: test] Error 1

```
---
<!-- COMMENTS:END -->
