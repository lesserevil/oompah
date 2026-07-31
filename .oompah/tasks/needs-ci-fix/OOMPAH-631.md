---
id: OOMPAH-631
type: bug
status: Needs CI Fix
priority: 1
title: Restore validation ownership when terminal retries coalesce
parent: OOMPAH-584
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T00:08:00.758352Z'
updated_at: '2026-07-31T00:34:58.522024Z'
work_branch: epic-OOMPAH-584--task-OOMPAH-631
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: a2a29335ee6182a0bd482858460eb19f1eb1be588b29354d79864987fde1d125
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Duplicate screening worker was terminated.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: '2026-07-31T00:27:45.046849+00:00'
oompah.agent_run_id: 7a8389ea-e98b-4684-a850-d63e707d978f
oompah.work_branch: epic-OOMPAH-584--task-OOMPAH-631
oompah.integration:
  version: 1
  state: blocked
  attempts: 1
  task_branch: epic-OOMPAH-584--task-OOMPAH-631
  base_branch: epic-OOMPAH-584
  base_sha: c03e52f66f4e5123576f4de3f21e4a763cc9c4b1
  head_sha: 0ae816c558a75f0461bd8d2910eab43f2fb70a33
  submitted_at: '2026-07-31T00:30:12.966418+00:00'
  updated_at: '2026-07-31T00:34:52.856161+00:00'
  last_error: "Combined-tree quality gate failed: ine 104, in close\n      proto.pipe.close()\n\
    \    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 568, in close\n      self._close(None)\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 592, in _close\n      self._loop.call_soon(self._call_connection_lost,\
    \ exc)\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 799, in call_soon\n      self._check_closed()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 545, in _check_closed\n      raise RuntimeError('Event loop is closed')\n\
    \  RuntimeError: Event loop is closed\n  \n  Enable tracemalloc to get traceback\
    \ where the object was allocated.\n  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))\n\
    \ntests/test_work_contributors.py::TestFireWorkContributorRecord::test_does_not_block\n\
    \  /home/shedwards/.oompah/worktrees/oompah/OOMPAH-631/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67:\
    \ PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__\
    \ at 0x79cf432e3600>\n  \n  Traceback (most recent call last):\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/pathlib.py\"\
    , line 441, in __str__\n      return self._str\n             ^^^^^^^^^\n  AttributeError:\
    \ 'PosixPath' object has no attribute '_str'\n  \n  During handling of the above\
    \ exception, another exception occurred:\n  \n  Traceback (most recent call last):\n\
    \    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/pathlib.py\"\
    , line 555, in drive\n      return self._drv\n             ^^^^^^^^^\n  AttributeError:\
    \ 'PosixPath' object has no attribute '_drv'\n  \n  During handling of the above\
    \ exception, another exception occurred:\n  \n  Traceback (most recent call last):\n\
    \    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 126, in __del__\n      self.close()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
    , line 104, in close\n      proto.pipe.close()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 568, in close\n      self._close(None)\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py\"\
    , line 592, in _close\n      self._loop.call_soon(self._call_connection_lost,\
    \ exc)\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 799, in call_soon\n      self._check_closed()\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py\"\
    , line 545, in _check_closed\n      raise RuntimeError('Event loop is closed')\n\
    \  RuntimeError: Event loop is closed\n  \n  Enable tracemalloc to get traceback\
    \ where the object was allocated.\n  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))\n\
    \n-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html\n===========================\
    \ short test summary info ============================\nFAILED tests/test_state_branch_migration.py::TestConcurrentWrite::test_shadow_write_tracker_serializes_writes\n\
    ===== 1 failed, 13826 passed, 7 skipped, 40 warnings in 248.85s (0:04:08) ======\n\
    make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-631'\n\
    \nUninstalled 8 packages in 13ms\nInstalled 8 packages in 15ms\nmake[1]: *** [Makefile:225:\
    \ test] Error 1\n"
oompah.task_costs:
  total_input_tokens: 1487463
  total_output_tokens: 12269
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 1487463
      output_tokens: 12269
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 1487295
    output_tokens: 12212
    cost_usd: 0.0
    recorded_at: '2026-07-31T00:20:22.442488+00:00'
  - profile: default
    model: haiku
    input_tokens: 168
    output_tokens: 57
    cost_usd: 0.0
    recorded_at: '2026-07-31T00:27:44.603524+00:00'
---
## Summary

Implementation scope: repair explicit terminal-transition retries that coalesce with an existing pending or in-progress audit while the task has drifted out of In Validation. A successful explicit retry must atomically restore nonterminal task state to In Validation under the project transition lock, and the API/CLI response must report the actual staged state rather than claiming In Validation when no tracker write occurred. Preserve idempotent audit IDs and do not regress already terminal or Archived tasks. Relevant code: oompah/terminal_transition_coordinator.py and terminal status API/CLI interfaces. Tests: reproduce a pending Done audit whose task was raced to Needs Human, retry the identical transition, and prove the same audit is retained, status is repaired, status_repaired/status_staged are truthful, no duplicate queued comment is posted, and concurrent calls remain serialized. Acceptance criteria: an operator retry cannot leave a pending audit stranded outside In Validation; focused coordinator/interface tests and the complete Makefile gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 00:08
---
Claimed directly by the operator Codex session because this bug is the live deadlock preventing OOMPAH-590 from re-entering validation. Implementation will begin after OOMPAH-630's exact head finishes its currently active integration gate, avoiding a moving-head race.
---
author: oompah
created: 2026-07-31 00:08
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 00:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 00:17
---
Duplicate screening scope only: no local server startup is needed. Search found no existing task for this exact coalesced-audit status repair; OOMPAH-630 is prerequisite context, not a duplicate. Please record the no-duplicate result and hand off to implementation now. The implementation branch should later integrate on top of OOMPAH-630's c03e52f66 exact head through the parent queue.
---
author: oompah
created: 2026-07-31 00:20
---
Operator takeover: duplicate screening has remained active for over ten minutes, attempted to start a second server from a read-only sandbox, and did not post a screening result or handoff. No duplicate exists; OOMPAH-630 is prerequisite context. Releasing the stale screening claim and implementing directly per the epic's fallback rule.
---
author: oompah
created: 2026-07-31 00:20
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 105
- Tokens: 1.5M in / 12.2K out [1.5M total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 43s
- Log: OOMPAH-631__20260731T000846Z.jsonl
---
author: oompah
created: 2026-07-31 00:26
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 00:26
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 00:27
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 11
- Tokens: 168 in / 57 out [225 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 3s
- Log: OOMPAH-631__20260731T002649Z.jsonl
---
author: oompah
created: 2026-07-31 00:30
---
Implemented and pushed exact head 0ae816c55. Explicit coalesced terminal retries now restore nonterminal drift to In Validation under the cross-loop project lock, preserve terminal states, avoid duplicate audits/comments, and expose truthful status_staged/status_repaired results across HTTP, CLI, and ACP. Verification on the reconstructed isolated worktree: 261 focused tests passed; terminal mutation scan passed. The same patch also passed the broader 573-test task/server/epic group before the managed-worktree reset (the one mock updated in the final patch was then re-run successfully).
---
author: oompah
created: 2026-07-31 00:30
---
Coalesced terminal retries can no longer strand a pending audit outside In Validation; interfaces now report actual staging state.
---
author: oompah
created: 2026-07-31 00:34
---
The combined-tree quality gate failed on `epic-OOMPAH-584--task-OOMPAH-631`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
ine 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

tests/test_work_contributors.py::TestFireWorkContributorRecord::test_does_not_block
  /home/shedwards/.oompah/worktrees/oompah/OOMPAH-631/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x79cf432e3600>
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/pathlib.py", line 441, in __str__
      return self._str
             ^^^^^^^^^
  AttributeError: 'PosixPath' object has no attribute '_str'
  
  During handling of the above exception, another exception occurred:
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/pathlib.py", line 555, in drive
      return self._drv
             ^^^^^^^^^
  AttributeError: 'PosixPath' object has no attribute '_drv'
  
  During handling of the above exception, another exception occurred:
  
  Traceback (most recent call last):
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
      self.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
      proto.pipe.close()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 568, in close
      self._close(None)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/unix_events.py", line 592, in _close
      self._loop.call_soon(self._call_connection_lost, exc)
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 799, in call_soon
      self._check_closed()
    File "/home/shedwards/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_events.py", line 545, in _check_closed
      raise RuntimeError('Event loop is closed')
  RuntimeError: Event loop is closed
  
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.
    warnings.warn(pytest.PytestUnraisableExceptionWarning(msg))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_state_branch_migration.py::TestConcurrentWrite::test_shadow_write_tracker_serializes_writes
===== 1 failed, 13826 passed, 7 skipped, 40 warnings in 248.85s (0:04:08) ======
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-631'

Uninstalled 8 packages in 13ms
Installed 8 packages in 15ms
make[1]: *** [Makefile:225: test] Error 1

```
---
<!-- COMMENTS:END -->
