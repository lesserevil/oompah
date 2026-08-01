---
id: OOMPAH-667
type: bug
status: In Validation
priority: 1
title: Keep Makefile virtualenv PATH from defeating canonical CLI cutover
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- ci-fix
assignee: null
created_at: '2026-07-31T21:32:57.017227Z'
updated_at: '2026-08-01T00:02:12.255560Z'
work_branch: OOMPAH-667
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/629
review_number: '629'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 7599962d7e4882dd14f44d8ceea52fc73864838b17354027b56d93f81b9e7418
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-07-31T22:58:51.200342+00:00'
  matched_identifiers: []
  evidence: "Based on my thorough investigation of the task database, I can now render\
    \ my duplicate screening verdict.\n\n## Investigation Summary\n\nI searched the\
    \ oompah task tracker across all states (open, merged, archived) using multiple\
    \ keyword combinations:\n- \"OOMPAH-619\" (the triggering issue mentioned) \u2014\
    \ not found in the database\n- \"sync-cli\", \"sync_canonical_cli\" \u2014 not\
    \ found\n- \"canonical\", \"launcher\", \"activation\" \u2014 not found\n- \"\
    Makefile\", \"virtualenv\", \"PATH\" \u2014 not found in task descriptions or\
    \ code context\n- Task ID ranges 600-669 (to capture 619 and 667) \u2014 no such\
    \ tasks exist\n\nThe only open task found was **OOMPAH-281** (self-hosted GitHub\
    \ Actions runner setup), which is unrelated to this PATH/CLI cutover issue.\n\n\
    ## Problem Analysis\n\nI confirmed the bug exists by examining the actual source\
    \ code:\n\n1. **Makefile** (line 4-5): Exports `PATH := $(abspath $(VENV)/bin):$(PATH)`\
    \ globally\n2. **sync_canonical_cli.py** (lines 450-481): The `synchronize()`\
    \ function validates that `command -v oompah` resolves to the canonical user launcher\
    \ at `~/.local/bin/oompah` using the operator's real PATH\n3. **The conflict**:\
    \ When `make sync-cli` is invoked, it runs the validation script with the Makefile-enhanced\
    \ PATH, causing `shutil.which(\"oompah\")` to find `.venv/bin/oompah` instead,\
    \ triggering the error: `refusing CLI synchronization: command -v oompah resolves\
    \ to .venv/bin/oompah; expected ~/.local/bin/oompah`\n\nThe issue is a unique,\
    \ reproducible problem with no existing duplicate task covering it.\n\n---\n\n\
    **Focus handoff: duplicate_detector**\n\n**Duplicate preflight verdict: no_duplicate**\n\
    \n**Matches: none**\n\n**Evidence:** Comprehensive scan of .oompah/tasks across\
    \ all states (archived, merged, open) using multiple search patterns (sync-cli,\
    \ canonical, launcher, PATH, Makefile, virtualenv, cutover) yielded no results.\
    \ OOMPAH-619 (referenced as the triggering issue) does not exist in the task database.\
    \ OOMPAH-281 (the only open task touching CLI infrastructure) covers self-hosted\
    \ GitHub A"
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 762bc01a-3a84-401c-b4b5-295694dde00a
oompah.task_costs:
  total_input_tokens: 3515913
  total_output_tokens: 25951
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 3515907
      output_tokens: 25472
      cost_usd: 0.0
    opus:
      input_tokens: 6
      output_tokens: 479
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 186
    output_tokens: 4766
    cost_usd: 0.0
    recorded_at: '2026-07-31T22:58:51.200004+00:00'
  - profile: default
    model: haiku
    input_tokens: 3515721
    output_tokens: 20706
    cost_usd: 0.0
    recorded_at: '2026-07-31T23:06:53.976253+00:00'
  - profile: deep
    model: opus
    input_tokens: 6
    output_tokens: 479
    cost_usd: 0.0
    recorded_at: '2026-07-31T23:35:41.518291+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-667__20260731T225718Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: OOMPAH-667
    source_sha: d96740a6ecdca353e40ef87e94a4ee91b8828df0
    completed_at: '2026-07-31T22:58:51.212689+00:00'
  - run_id: OOMPAH-667__20260731T225912Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: event_api
    source_branch: OOMPAH-667
    source_sha: 6ee3e02133d9f8668597285110e480069d92c6af
    completed_at: '2026-07-31T23:06:53.984426+00:00'
  - run_id: OOMPAH-667__20260731T231532Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: ci_fix
    source_branch: OOMPAH-667
    source_sha: 669094c81f4b2d52431134b99f084878223785dc
    completed_at: '2026-07-31T23:35:41.521212+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-667
  base_branch: main
  base_sha: 9fc14256e7912023844663ddfee2a9940c71e05f
  head_sha: 669094c81f4b2d52431134b99f084878223785dc
  submitted_at: '2026-07-31T23:35:16.004331+00:00'
  updated_at: '2026-07-31T23:35:46.499887+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/629
oompah.review_number: '629'
oompah.work_branch: OOMPAH-667
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-e0d3e435db98: '2026-08-01T00:02:07.669699+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-667
    target_state: Done
    evidence_fingerprint: c8c5cbe715ac16fca6fd06860bbe3555d86dd3f0fb69240521fe555ea9a0e588
    audit_ids:
    - audit-aa5f1643fa3e
    kind: result
    applied: true
    retired_at: '2026-08-01T00:02:07.669708+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-667
    audit_id: audit-aa5f1643fa3e
    attempt_id: attempt-e0d3e435db98
    target_state: Done
    evidence_fingerprint: c8c5cbe715ac16fca6fd06860bbe3555d86dd3f0fb69240521fe555ea9a0e588
    status: In Validation
    audit_ids:
    - audit-aa5f1643fa3e
    applied: true
    created_at: '2026-08-01T00:02:07.669720+00:00'
    applied_at: '2026-08-01T00:02:11.414612+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-aa5f1643fa3e
    project_id: proj-14849f1b
    task_id: OOMPAH-667
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c8c5cbe715ac16fca6fd06860bbe3555d86dd3f0fb69240521fe555ea9a0e588
    attempts:
    - version: 1
      attempt_id: attempt-e0d3e435db98
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: c8c5cbe715ac16fca6fd06860bbe3555d86dd3f0fb69240521fe555ea9a0e588
      created_at: '2026-08-01T00:00:02.004895+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-01T00:00:02.004895+00:00'
      branch_key: OOMPAH-667
      verdict: pass
      completed_at: '2026-08-01T00:02:07.669604+00:00'
      ended_at: '2026-08-01T00:02:07.669604+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T23:58:43.595561+00:00'
    updated_at: '2026-08-01T00:02:07.669604+00:00'
  - version: 1
    audit_id: audit-9c0d35990825
    project_id: proj-14849f1b
    task_id: OOMPAH-667
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c8c5cbe715ac16fca6fd06860bbe3555d86dd3f0fb69240521fe555ea9a0e588
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-07-31T23:58:43.595561+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e0d3e435db98
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: c8c5cbe715ac16fca6fd06860bbe3555d86dd3f0fb69240521fe555ea9a0e588
    created_at: '2026-08-01T00:00:02.004895+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-01T00:00:02.004895+00:00'
    branch_key: OOMPAH-667
---
## Summary

Triggered by: OOMPAH-619

Production reproduction on merged main revision 16362384be835d1485d1121ce3c8329743391c79: running make sync-cli with the normal Makefile environment fails with "refusing CLI synchronization: command -v oompah resolves to .venv/bin/oompah; expected ~/.local/bin/oompah". Makefile globally prepends the project virtualenv to PATH so its internal Python and tools are available, but scripts/sync_canonical_cli.py correctly treats that same effective PATH as the operator command-resolution contract. The supported operational workaround make PATH="$PATH" sync-cli and make PATH="$PATH" restart succeeds, proving the selected revision and cutover logic are sound. Fix the Makefile and/or lifecycle scripts so internal virtualenv tool resolution is separated from validation of the caller/canonical CLI PATH; do not weaken detection of a genuinely shadowing noncanonical oompah executable. Add regression tests that invoke the real sync-cli and restart target environment with isolated HOME, UV tool directories, virtualenv, and canonical launcher; cover initial activation, already-current no-op, a true wrong-PATH refusal, install failure rollback, and successful server/CLI revision equality. Acceptance: unqualified make sync-cli and normal make restart work from a standard operator shell, command -v oompah still resolves to the canonical user launcher after cutover, CLI/server revisions match, and the focused lifecycle suites plus full project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 22:57
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 22:57
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-31 22:58
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 51, Tool calls: 25
- Tokens: 186 in / 4.8K out [5.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 39s
- Log: OOMPAH-667__20260731T225718Z.jsonl
---
author: oompah
created: 2026-07-31 22:59
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-31 22:59
---
Focus: Event Api Redaction Specialist
---
author: oompah
created: 2026-07-31 22:59
---
Understanding: the Makefile's virtualenv PATH must support internal tooling without changing the PATH used to validate the canonical user CLI. I will trace the lifecycle scripts and existing tests, implement the smallest separation, add coverage for sync/restart success and refusal/rollback cases, then run focused checks.
---
author: oompah
created: 2026-07-31 23:01
---
Discovery: Makefile line 3 prepends .venv/bin globally, and restart's recursive make would otherwise re-capture that polluted PATH. The safe design is to capture OOMPAH_OPERATOR_PATH before export, export it for recursive targets, and pass --operator-path to sync/start/restart/force-restart. sync_canonical_cli and canonical_cli_cutover will keep internal PATH for UV/Python while using the explicit operator path for strict launcher resolution and CLI verification.
---
author: oompah
created: 2026-07-31 23:05
---
Implementation: captured the pre-virtualenv PATH as OOMPAH_OPERATOR_PATH in Makefile (including recursive make), passed it via --operator-path through sync-cli/start/restart/force-restart, and added explicit operator-path handling to both lifecycle scripts. Internal UV/Python staging remains on the exported venv PATH; canonical resolution/version checks use the preserved operator PATH. Added shadowing/no-op/refusal and CLI/server equality regressions plus updated cli-install documentation.
---
author: oompah
created: 2026-07-31 23:05
---
Verification: focused lifecycle and neighboring Makefile suites pass: 97 passed in 16.41s (test_canonical_cli_sync.py, test_lifecycle_cli_sync_integration.py, test_makefile_setup.py, test_makefile_restart_wait.py). Python compilation and both helper --help checks pass; git diff --check is clean. Make dry-runs confirm sync/restart receive the preserved operator PATH.
---
author: oompah
created: 2026-07-31 23:06
---
Completion: pushed commit 6ee3e0213 to origin/OOMPAH-667. Make lifecycle commands now preserve the caller's canonical CLI PATH while retaining internal venv tooling, strict shadowing refusal remains intact, focused suites are green, and the worktree is clean/up to date.
---
author: oompah
created: 2026-07-31 23:06
---
Preserved operator CLI PATH through Make lifecycle and added regression coverage
---
author: oompah
created: 2026-07-31 23:06
---
Agent completed successfully in 466s (3536427 tokens)
---
author: oompah
created: 2026-07-31 23:06
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 63
- Tokens: 3.5M in / 20.7K out [3.5M total]
- Cost: $0.0000
- Exit: normal, Duration: 7m 46s
- Log: OOMPAH-667__20260731T225912Z.jsonl
---
author: oompah
created: 2026-07-31 23:14
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-667`
Target: `main`
Head: `6ee3e02133d9f8668597285110e480069d92c6af`
Command: `make test`
Result: `failed`

Required: run the command in the task worktree, fix the failure, commit and push the repair, then leave the task in Done. Oompah will rerun the gate for the new head before creating the PR/MR.

Output tail:
```text
e/.venv/lib/python3.12/site-packages/httpx/_models.py:408: DeprecationWarning: Use 'content=<...>' to upload raw bytes/text content.
    headers, stream = encode_request(

tests/test_webhooks.py::TestForwarderProcessFullLifecycle::test_polling_resume_when_forwarder_process_dies
  /home/shedwards/.oompah/tmp/oompah-quality-gate-tm10yr91/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7ea0e59e3920>
  
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

tests/test_webhooks.py::TestForwarderProcessFullLifecycle::test_process_start_and_immediate_exit
  /home/shedwards/.oompah/tmp/oompah-quality-gate-tm10yr91/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7c8debf9b920>
  
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
FAILED tests/test_orchestrator_handlers.py::TestTickDelegation::test_tick_notifies_observers
= 1 failed, 14542 passed, 8 skipped, 1 xfailed, 45 warnings in 415.04s (0:06:55) =

make: *** [Makefile:381: test] Error 1
```
---
author: oompah
created: 2026-07-31 23:15
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-07-31 23:15
---
Focus: CI Failure Fixer
---
author: oompah
created: 2026-07-31 23:15
---
Understanding: gate failed on tests/test_orchestrator_handlers.py::TestTickDelegation::test_tick_notifies_observers — unrelated to Makefile PATH work but blocks merge. Investigating that test to determine if my changes broke it, a rebase interaction with OOMPAH-668, or if it's a flaky/preexisting failure.
---
author: oompah
created: 2026-07-31 23:32
---
Discovery: gate failure is tests/test_orchestrator_handlers.py::TestTickDelegation::test_tick_notifies_observers, which passes ~10/10 locally in isolation and passes under xdist -n 8 loadgroup here too. My branch does not touch orchestrator.py or that test file. Root cause is a flaky race: _tick() fires _run_step5b_maintenance, _run_step5c_epic_maintenance, and _maybe_run_watchdog (on the tick_pool) plus real _recover_release_addendum_leases, and any of these can transitively touch _notify_observers under load. Fix pattern is the same one OOMPAH-652 applied to TestRunStep5cEpicMaintenance: mock the fire-and-forget maintenance methods so the assert_called_once() invariant is deterministic.
---
author: oompah
created: 2026-07-31 23:35
---
Verification: TestTickDelegation now 7/7 passes on repeated runs; whole tests/test_orchestrator_handlers.py file (277 tests) passes under xdist -n 8 --dist loadgroup. Pushed 669094c81 to origin/OOMPAH-667. Ready for the gate rerun.
---
author: oompah
created: 2026-07-31 23:35
---
Preserved operator CLI PATH in Make lifecycle and stabilized the tick observer-notification tests. The lifecycle work (6ee3e0213) captures OOMPAH_OPERATOR_PATH before the Makefile prepends .venv/bin/, passes --operator-path through sync-cli/start/restart/force-restart, and separates internal UV/Python tooling PATH from operator canonical CLI validation so unqualified make sync-cli and make restart work from a standard shell without weakening shadow detection. The gate fix (669094c81) mocks the fire-and-forget maintenance methods (_maybe_run_watchdog, _run_step5b_maintenance, _run_step5c_epic_maintenance, _recover_release_addendum_leases) on both TestTickDelegation notify tests so assert_called_once is deterministic under xdist CPU contention. Focused suites (canonical_cli_sync, lifecycle_cli_sync_integration, makefile_setup, makefile_restart_wait, orchestrator_handlers full file) pass locally.
---
author: oompah
created: 2026-07-31 23:35
---
Agent completed successfully in 1214s (485 tokens)
---
author: oompah
created: 2026-07-31 23:35
---
Run #YOLO-reopen [attempt=YOLO-reopen, profile=deep, role=deep -> Claude/opus]
- Turns: 153, Tool calls: 108
- Tokens: 6 in / 479 out [485 total]
- Cost: $0.0000
- Exit: normal, Duration: 20m 14s
- Log: OOMPAH-667__20260731T231532Z.jsonl
---
author: oompah
created: 2026-07-31 23:49
---
Branch quality gate passed for `669094c81f4b2d52431134b99f084878223785dc` using `make test` in 398.0s. Review creation may proceed.
---
author: oompah
created: 2026-07-31 23:58
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-07-31 23:58
---
YOLO: merged PR #629.
---
author: oompah
created: 2026-08-01 00:00
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-01 00:00
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-01 00:02
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- merge_commit: 8fe9439ff6589d076e210a3c7bf0292f54661d8a
- branch_head: 669094c81f4b2d52431134b99f084878223785dc
- gate_result: passed 398s, 14542 passed 8 skipped 1 xfailed
- commits: 6ee3e0213 (Makefile+scripts), 669094c81 (test flake fix)
- key_tests: test_operator_path_ignores_internal_virtualenv_launcher, test_wrong_operator_path_still_refuses_shadowing_launcher, test_already_current_is_a_noop, test_failed_install_or_mismatch_preserves_known_good_cli
---
<!-- COMMENTS:END -->
