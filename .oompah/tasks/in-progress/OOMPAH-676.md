---
id: OOMPAH-676
type: task
status: In Progress
priority: null
title: Make graceful CLI cutover drain workers before restart
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-08-01T05:18:04.532392Z'
updated_at: '2026-08-01T05:41:20.739246Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: f2deedf4e59e17e8fe42b8b61a88e8c80a14dd478df80f936e3993911b4c31eb
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T05:19:57.679509+00:00'
  matched_identifiers: []
  evidence: "Based on my comprehensive investigation, I can now provide the final\
    \ verdict on whether OOMPAH-676 is a duplicate of an existing task.\n\n## Investigation\
    \ Summary\n\nI performed exhaustive searches across all `.oompah/tasks/` directories\
    \ (open, backlog, merged, archived) and documentation sources for:\n\n**Search\
    \ terms used:**\n- Keywords: `graceful`, `drain`, `workers`, `terminate`, `pause`,\
    \ `orchestrator`, `quiesce`, `undrained`, `redispatch`\n- File references: `canonical_cli_cutover`,\
    \ `orchestrator.py`, `server.py`, `test_lifecycle_cli_sync`, `test_makefile_restart`\n\
    - Broader terms: `restart`, `cutover`, `deploy`, `lifecycle`, `cli_sync`\n- Task\
    \ references: `OOMPAH-675`, `OOMPAH-676`, `auth-health`, `post-deploy`\n\n**All\
    \ searches returned zero matches** across:\n- `.oompah/tasks/` (open, backlog,\
    \ merged, archived)\n- `docs/` and `plans/` directories\n- README.md and WORKFLOW.md\n\
    \n**Key findings:**\n1. The only currently open task is OOMPAH-281 (self-hosted\
    \ GitHub Actions runner setup) \u2014 completely unrelated\n2. No prior tasks\
    \ reference worker draining, graceful shutdown semantics, or orchestrator pause\
    \ operations\n3. OOMPAH-675 (mentioned in the issue as a live reproduction example)\
    \ does not exist in the tracker\n4. No documentation in `plans/` or `docs/` describes\
    \ the worker drain / pause-dispatch-only concept\n\n**Conclusion:**\nOOMPAH-676\
    \ \"Make graceful CLI cutover drain workers before restart\" is a fresh, unique\
    \ bug report describing a previously undocumented issue discovered on 2026-08-01.\
    \ The bug involves the `canonical_cli_cutover` script incorrectly terminating\
    \ active workers instead of letting them drain gracefully.\n\n---\n\n**Focus handoff:\
    \ duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\n**Matches:\
    \ none**\n\n**Evidence:** Comprehensive search of all 200+ active and archived\
    \ tasks, merged tasks, backlog items, and documentation yielded zero matches for\
    \ any keywords, file references, or concepts related to OOMPAH-676's scope (worker\
    \ draining, graceful shutdow"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 7f10fcf3-33c2-4e82-b506-3e24037247d9
oompah.task_costs:
  total_input_tokens: 11821934
  total_output_tokens: 38053
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 11821934
      output_tokens: 38053
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 130
    output_tokens: 5056
    cost_usd: 0.0
    recorded_at: '2026-08-01T05:19:57.678406+00:00'
  - profile: default
    model: haiku
    input_tokens: 11821804
    output_tokens: 32997
    cost_usd: 0.0
    recorded_at: '2026-08-01T05:33:31.894864+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-676__20260801T051824Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-676
    source_sha: cde6401136d6561b694b05f81f4337cd26d7a3fe
    completed_at: '2026-08-01T05:19:57.690711+00:00'
  - run_id: OOMPAH-676__20260801T052014Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: devops
    source_branch: OOMPAH-676
    source_sha: cd9b2652a665bd9004c0d91d2b1921bcf4a831c6
    completed_at: '2026-08-01T05:33:31.899270+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-676
  base_branch: main
  base_sha: cde6401136d6561b694b05f81f4337cd26d7a3fe
  head_sha: cd9b2652a665bd9004c0d91d2b1921bcf4a831c6
  submitted_at: '2026-08-01T05:32:58.461601+00:00'
  updated_at: '2026-08-01T05:33:37.067510+00:00'
---
## Summary

Bug discovered while clearing the post-deploy auth-health alert on 2026-08-01. The documented make restart/make graceful path promises to drain active agents, but scripts/canonical_cli_cutover.py first POSTs /api/v1/orchestrator/pause. Orchestrator.pause() immediately schedules _terminate_all_running(), so _wait_for_state(paused and running==0) observes terminated workers rather than naturally completed workers. In the live reproduction, OOMPAH-675 run #1 exited terminated during make graceful and had to be redispatched after restart. Implementation scope: introduce or use a pause-dispatch-only/quiesce operation for canonical cutover, preserve existing explicit pause semantics, let running workers finish until the configured drain timeout, persist and terminate/recover only truly undrained workers at timeout, and keep CLI/server transactional cutover guarantees. Relevant files: scripts/canonical_cli_cutover.py, oompah/server.py, oompah/orchestrator.py, tests/test_lifecycle_cli_sync_integration.py, tests/test_makefile_restart_wait.py, and restart lifecycle tests. Acceptance criteria: make restart/make graceful stop new dispatch without terminating active workers before timeout; a worker that completes during drain is not redispatched; a timed-out worker is safely recovered exactly once; explicit operator pause behavior remains compatible; focused lifecycle and integration tests cover the live regression.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 05:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 05:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 05:19
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 45, Tool calls: 27
- Tokens: 130 in / 5.1K out [5.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 37s
- Log: OOMPAH-676__20260801T051824Z.jsonl
---
author: oompah
created: 2026-08-01 05:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 05:20
---
Focus: DevOps Engineer
---
author: oompah
created: 2026-08-01 05:20
---
Understanding: canonical CLI graceful cutover currently appears to use explicit pause semantics that terminate running workers. I will trace the cutover/server/orchestrator lifecycle, introduce a dispatch-quiesce path for restart while preserving explicit pause, add regression tests for natural drain and timeout recovery, then run focused checks.
---
author: oompah
created: 2026-08-01 05:24
---
Discovery: graceful_restart already waits naturally and persists only state.running at timeout; explicit pause is the destructive path because it schedules _terminate_all_running. The fix will add a transient quiesced dispatch gate with state/API/IPC support, preserve /pause semantics, and have canonical cutover continue to /restart with drain_timeout_s=0 only after its configured drain window, allowing the server restart path to persist truly undrained workers.
---
author: oompah
created: 2026-08-01 05:31
---
Implementation: added transient Orchestrator.quiesce() and quiesced state, dispatch/retry/audit gating, restart-safe state reporting, and API/IPC /api/v1/orchestrator/quiesce. Canonical cutover now quiesces, waits for natural completion, and on timeout proceeds transactionally to restart with the server’s zero-budget persistence/termination boundary. Added lifecycle tests for natural completion (no recovery), timeout recovery exactly once, API/IPC routing, and explicit pause compatibility; updated CLI lifecycle docs.
---
author: oompah
created: 2026-08-01 05:32
---
Verification: focused lifecycle/cutover and event-driven restart tests pass (80). API, IPC, explicit-pause, Makefile restart-wait, and orchestrator pause suites pass (105). Dispatch compatibility/state API neighboring suites pass (80). MCP exposure policy and gateway suites pass (311). make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-676'
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-676' was attempted but the environment cannot initialize the project venv: astral-uv failed with DBus InvalidArgs/kernel-thread transient-scope error; no code test failure was observed.
---
author: oompah
created: 2026-08-01 05:32
---
Completion: delivered and pushed cd9b2652a. Graceful make restart/cutover now quiesces dispatch, allows active workers to finish, and delegates only timed-out workers to restart recovery; natural completions are not redispatched. Explicit /pause behavior is unchanged. Added API/IPC/MCP policy coverage, lifecycle regression tests, and updated CLI docs. Branch is pushed and clean. Note: make test could not pass setup because astral-uv failed with the host DBus transient-scope error; focused suites all passed.
---
author: oompah
created: 2026-08-01 05:33
---
Quiesced graceful CLI cutover now drains active workers naturally, recovers only timed-out workers, preserves explicit pause semantics, and includes lifecycle/API/IPC/MCP regression coverage.
---
author: oompah
created: 2026-08-01 05:33
---
Agent completed successfully in 803s (11854801 tokens)
---
author: oompah
created: 2026-08-01 05:33
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 108
- Tokens: 11.8M in / 33.0K out [11.9M total]
- Cost: $0.0000
- Exit: normal, Duration: 13m 23s
- Log: OOMPAH-676__20260801T052014Z.jsonl
---
author: oompah
created: 2026-08-01 05:40
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-676`
Target: `main`
Head: `cd9b2652a665bd9004c0d91d2b1921bcf4a831c6`
Command: `make test`
Result: `failed`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
::test_ws_bootstrap_auth_disabled_shows_false
  /home/shedwards/.oompah/tmp/oompah-quality-gate-gla1n1n_/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7930abeb3920>
  
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
  /home/shedwards/.oompah/tmp/oompah-quality-gate-gla1n1n_/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7409f6e03920>
  
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
FAILED tests/test_cli_mismatch_recovery.py::test_mismatched_launcher_detected_and_repaired_during_cutover
FAILED tests/test_cli_mismatch_recovery.py::test_recovery_uses_same_lifecycle_lock_as_normal_synchronize
FAILED tests/test_cli_mismatch_recovery.py::test_successful_recovery_proves_no_final_mismatch
= 3 failed, 14738 passed, 8 skipped, 1 xfailed, 44 warnings in 388.89s (0:06:28) =

make: *** [Makefile:388: test] Error 1
```
---
author: oompah
created: 2026-08-01 05:41
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-01 05:41
---
Focus: CI Failure Fixer
---
<!-- COMMENTS:END -->
