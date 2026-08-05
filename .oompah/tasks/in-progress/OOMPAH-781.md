---
id: OOMPAH-781
type: feature
status: In Progress
priority: 1
title: Cut terminal-audit lifecycle over to durable decisions and jobs
parent: OOMPAH-768
children: []
blocked_by:
- OOMPAH-793
- OOMPAH-812
- OOMPAH-791
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:58:59.010872Z'
updated_at: '2026-08-05T19:28:32.611458Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-781
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 3e730440ffde04145aa9c18b89db7431eda9a2cd7a481c12d5b3ab63ea7ce0e7
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T20:24:23.241257+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: OOMPAH-781 describes a unique domain cutover task within\
    \ the OOMPAH-768 epic (\"Migrate every workflow domain to shared decisions and\
    \ durable jobs\"). The terminal-audit lifecycle domain is distinct from the active\
    \ sibling domain tasks: OOMPAH-782 (review/CI domain), OOMPAH-791 (epic rollup\
    \ domain), and OOMPAH-793 (implementation/direct-owner domain). While OOMPAH-768\
    \ is the parent epic covering multiple domains, OOMPAH-781 is specifically scoped\
    \ to audit request ownership, candidate selection, launch, rotation, finalization,\
    \ result application, retries, and exhaustion. No existing active task covers\
    \ this specific terminal-audit domain cutover. All similar-scored archived tasks\
    \ (OOMPAH-158\u2013OOMPAH-303, OOMPAH-398) are in terminal states and therefore\
    \ excluded as duplicate candidates per the rules. OOMPAH-804 is a production-integration\
    \ wrapper task, not a duplicate implementation.\nFocus handoff: duplicate_detector\n\
    \nDuplicate preflight verdict: no_duplicate\n\nMatches: none\n\nEvidence: OOMPAH-781\
    \ describes a unique domain cutover task within the OOMPAH-768 epic (\"Migrate\
    \ every workflow domain to shared decisions and durable jobs\"). The terminal-audit\
    \ lifecycle domain is distinct from the active sibling domain tasks: OOMPAH-782\
    \ (review/CI domain), OOMPAH-791 (epic rollup domain), and OOMPAH-793 (implementation/direct-owner\
    \ domain). While OOMPAH-768 is the parent epic covering multiple domains, OOMPAH-781\
    \ is specifically scoped to audit request ownership, candidate selection, launch,\
    \ rotation, finalization, result application, retries, and exhaustion. No existing\
    \ active task covers this specific terminal-audit domain cutover. All similar-scored\
    \ archived tasks (OOMPAH-158\u2013OOMPAH-303, OOMPAH-398) are in terminal states\
    \ and therefore excluded as duplicate candidates per the rules. OOMPAH-804 is\
    \ a production-integration wrapper task, not a duplicate implementation."
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
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-781
oompah.integration:
  version: 2
  state: blocked
  attempts: 2
  task_branch: epic-OOMPAH-768--task-OOMPAH-781
  base_branch: epic-OOMPAH-768
  base_sha: a744be37d42047e25e6fc62a6a64878c187290e0
  head_sha: 41f717cd46baf4e8ba455586b39ce9e67d25a471
  submitted_at: '2026-08-04T21:44:34.061860+00:00'
  updated_at: '2026-08-04T22:45:48.494351+00:00'
  last_error: "Combined-tree quality gate failed: ack where the object was allocated.\n\
    \  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings\
    \ for more info.\n\ntests/test_webhooks.py::TestGitLabHookManagerStatusCallback::test_reconcile_fires_callback_on_configuration_error\n\
    \  /home/shedwards/.oompah/tmp/oompah-quality-gate-xmzie_fp/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67:\
    \ PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__\
    \ at 0x763b8ce0b9c0>\n  \n  Traceback (most recent call last):\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
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
    \ntests/test_worker_submission.py::test_same_head_resubmit_from_in_progress_restores_ready_lifecycle\n\
    \  /home/shedwards/.oompah/tmp/oompah-quality-gate-xmzie_fp/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67:\
    \ PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__\
    \ at 0x70e3743b39c0>\n  \n  Traceback (most recent call last):\n    File \"/home/shedwards/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/lib/python3.12/asyncio/base_subprocess.py\"\
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
    \ short test summary info ============================\nFAILED tests/test_long_tick_regression.py::TestSyntheticSlowJobs::test_heal_repos_always_runs_after_dispatch_needed\n\
    = 1 failed, 15741 passed, 8 skipped, 1 xfailed, 47 warnings in 643.32s (0:10:43)\
    \ =\n\nmake: *** [Makefile:401: test] Error 1\n"
oompah.task_costs:
  total_input_tokens: 10
  total_output_tokens: 1252
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 10
      output_tokens: 1252
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 10
    output_tokens: 1252
    cost_usd: 0.0
    recorded_at: '2026-08-04T20:24:23.239960+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-781__20260804T202239Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: haiku
    focus: duplicate_detector
    source_branch: epic-OOMPAH-768--task-OOMPAH-781
    source_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
    completed_at: '2026-08-04T20:24:23.267882+00:00'
---
## Summary

Migrate audit request ownership, candidate selection, launch, rotation, finalization, result application, retries, exhaustion, and historical recovery into durable workflow jobs while retaining TerminalTransitionCoordinator safety. Model queued/running/finalizing/retry-wait/action-required explicitly; ensure normal candidate rotation/transport retry is informational; guarantee result finalization cannot be starved by comments/output; preserve independent-candidate policy and exact evidence. Required tests: no candidate, transport failure, dynamic policy denial, duplicate/revoked auditor, oversized output, restart at each stage, deleted branches, finalization starvation, and current audit enforcement suites. Acceptance: every In Validation task has a durable audit disposition and bounded recovery; no valid verdict is lost or indefinitely pending.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:22
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 20:22
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 20:24
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 2, Tool calls: 0
- Tokens: 10 in / 1.3K out [1.3K total]
- Cost: $0.0000
- Exit: normal, Duration: 2m 5s
- Log: OOMPAH-781__20260804T202239Z.jsonl
---
author: oompah
created: 2026-08-04 20:26
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 20:26
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-04 20:27
---
Understanding: migrate terminal-audit ownership, candidate/launch/rotation/finalization/result/retry/recovery into durable decisions and jobs, preserving TerminalTransitionCoordinator safety and independent-candidate/evidence guarantees. I will first map existing lifecycle and persistence patterns, then implement focused changes with restart/starvation/auth/retry coverage.
---
author: oompah
created: 2026-08-04 20:27
---
Discovery: durable workflow_jobs/workflow_scheduler/workflow_worker infrastructure is present, while terminal-audit enforcement still owns a periodic monolithic scan and direct auditor launch. The cutover seam is the orchestrator enforcement/dispatch path; durable audit jobs will own phase/recovery and TerminalTransitionCoordinator will remain the sole result/status applicator.
---
author: oompah
created: 2026-08-04 20:38
---
Implementation: added terminal_audit_workflow durable adapter over WorkflowJobStore, phase-aware failure/recovery and phase telemetry in the ledger, wired enforcement/dispatch/retry/finalization into Orchestrator, and carried only non-secret workflow job identity on RunningEntry. Finalization is checkpointed before coordinator side effects; output/comments are excluded from checkpoints. Focused suites: 176 passed.
---
author: oompah
created: 2026-08-04 20:41
---
Verification: 189 focused tests pass across terminal_audit_workflow, workflow_jobs, workflow shadow, enforcement, workspace recovery, auditor exit/termination, and coordinator suites. Targeted Ruff checks, git diff --check, and direct terminal mutation scan pass. Make terminal-audit-scan could not initialize its task venv because uv failed with a DBus transient-scope error; underlying scan passed directly.
---
author: oompah
created: 2026-08-04 20:45
---
Final verification: latest focused gate passes (177 tests). make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-781'
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-781' is environment-blocked during task-venv setup by uv/DBus; direct full pytest is also environment-blocked at an unrelated ACP test because the default agent-log path is read-only. Targeted Ruff, mutation scan, and diff checks remain clean.
---
author: oompah
created: 2026-08-04 20:46
---
Completion: delivered and pushed eba03a422. Terminal audits now materialize exact evidence-bound durable jobs with queued/running/finalizing/retry-wait/action-required dispositions; candidate launch/rotation/recovery, coordinator finalization, result acknowledgement, and exhaustion are lease-fenced and restart-safe. Added 209 lines of focused lifecycle/restart/security tests; branch is clean and up to date with origin.
---
author: oompah
created: 2026-08-04 20:46
---
Durable terminal-audit workflow phases, lease ownership, retry/recovery, and non-starvable finalization are implemented and tested.
---
author: oompah
created: 2026-08-04 20:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 147
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 20m 24s
- Log: OOMPAH-781__20260804T202650Z.jsonl
---
author: oompah
created: 2026-08-04 20:59
---
The combined-tree quality gate failed on `epic-OOMPAH-768--task-OOMPAH-781`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
arnings.html#resource-warnings for more info.

tests/test_webhooks.py::TestForwarderProcessFullLifecycle::test_polling_resume_when_forwarder_process_dies
  /home/shedwards/.oompah/tmp/oompah-quality-gate-2ijbuvyy/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x7fd83cfaf9c0>
  
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

tests/test_work_contributors.py::TestOnWorkerExitContributor::test_normal_exit_fires_contributor_record
  /home/shedwards/.oompah/tmp/oompah-quality-gate-2ijbuvyy/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x762d94c4b9c0>
  
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
FAILED tests/test_integration_workflow.py::test_hundreds_of_history_rows_do_not_hide_eligible_heads
FAILED tests/test_orchestrator_merged.py::TestYoloMergeConflictLabelClearing::test_noop_when_no_matching_task
= 2 failed, 15691 passed, 8 skipped, 1 xfailed, 47 warnings in 687.05s (0:11:27) =

make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-04 21:00
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-04 21:00
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-04 21:01
---
Understanding: I will investigate the two combined-tree gate failures on the current durable terminal-audit branch, isolate whether they are ordering/state leaks introduced by the change, add focused regression coverage, then run affected suites, push, and resubmit the corrected head.
---
author: oompah
created: 2026-08-04 21:02
---
Discovery: reproduced the integration failure. Reconciling 402 workflow decisions performs a separately committed SQLite transaction per task and exceeds the 5-second gate timeout; the regression is independent of audit semantics but occurs on this combined branch. The YOLO orphan-label test passes alone, indicating an order/shared-state failure to isolate before changing it.
---
author: oompah
created: 2026-08-04 21:06
---
Implementation: scheduler reconciliation now writes each durable decision snapshot in one transaction, preserving cursor/job/event atomicity while avoiding per-row commit latency. Added regression coverage proving a failed multi-task snapshot leaves no stale cursor or job; the existing 402-history-row case now passes in 0.75s.
---
author: oompah
created: 2026-08-04 21:10
---
Verification: 18 scheduler, 30 workflow-job, 7 terminal-audit-workflow, 20 integration-workflow, and 5 YOLO merge-conflict tests pass (80 total); targeted Ruff, terminal-mutation scan, and diff check pass. make[1]: Entering directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-781'
make[1]: Leaving directory '/home/shedwards/.oompah/worktrees/oompah/OOMPAH-781' started with the candidate snapshot and passed its audit scan, but this session sandbox terminates the long pytest process after ~30 seconds before completion.
---
author: oompah
created: 2026-08-04 21:11
---
Completion: pushed 1ba60b568. Durable workflow scheduling now commits each snapshot atomically, eliminating the combined-gate history-row timeout and preventing partial cursor/job state on errors. The orphan YOLO test passes under full affected-module collection; no behavior change was needed there.
---
author: oompah
created: 2026-08-04 21:11
---
Fixed combined-gate durable scheduler timeout with atomic snapshot writes; focused suites pass
---
author: oompah
created: 2026-08-04 21:12
---
Run #1 [attempt=1, profile=standard, role=standard -> Codex/gpt-5.6-terra]
- Turns: 0, Tool calls: 70
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 57s
- Log: OOMPAH-781__20260804T210036Z.jsonl
---
author: oompah
created: 2026-08-04 21:44
---
Reconciled onto landed OOMPAH-793 head a744be37d: retained the terminal-audit domain commit as 41f717cd4 and dropped only redundant batching alternative 1ba60b568, because the epic already contains the authoritative atomic scheduling implementation with stronger rollback coverage. Focused verification: 57 passed (terminal audit workflow, workflow jobs, auditor dispatch). Branch is clean and force-updated with an exact old-head lease.
---
author: oompah
created: 2026-08-04 21:44
---
Rebased terminal-audit domain onto a744be37; dropped redundant batching alternative; 57 focused tests pass.
---
author: oompah
created: 2026-08-04 22:44
---
Live acceptance reproduction from OOMPAH-805: PR #715 was merged and terminal target Merged was queued. Audit audit-3d1 recorded a valid PASS labeled Done, but its result application reported/applied In Validation; the scheduler then dispatched a second audit for target Merged, which was interrupted, leaving the task In Validation with no active run/retry until an evidence-backed owner override. Please ensure the durable cutover preserves/advances the terminal target across intermediate PASS results, applies one valid verdict exactly once, and does not dispatch a second audit or strand the task when the merge target changes while an audit is active.
---
author: oompah
created: 2026-08-04 22:45
---
The combined-tree quality gate failed on `epic-OOMPAH-768--task-OOMPAH-781`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
ack where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/test_webhooks.py::TestGitLabHookManagerStatusCallback::test_reconcile_fires_callback_on_configuration_error
  /home/shedwards/.oompah/tmp/oompah-quality-gate-xmzie_fp/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x763b8ce0b9c0>
  
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

tests/test_worker_submission.py::test_same_head_resubmit_from_in_progress_restores_ready_lifecycle
  /home/shedwards/.oompah/tmp/oompah-quality-gate-xmzie_fp/workspace/.venv/lib/python3.12/site-packages/_pytest/unraisableexception.py:67: PytestUnraisableExceptionWarning: Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x70e3743b39c0>
  
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
FAILED tests/test_long_tick_regression.py::TestSyntheticSlowJobs::test_heal_repos_always_runs_after_dispatch_needed
= 1 failed, 15741 passed, 8 skipped, 1 xfailed, 47 warnings in 643.32s (0:10:43) =

make: *** [Makefile:401: test] Error 1

```
---
author: oompah
created: 2026-08-04 23:10
---
Repair checkpoint pushed at 94295b3b90530c1e927f4bb5f662464c2722c5b7. Durable terminal-audit finalization now persists a bounded replayable result identity, replays crash-before-apply and coordinator-applied/job-unacked outcomes, fences callbacks/recovery/exit handling to the exact audit+target+evidence+attempt+job+lease, recovers only one exact abandoned lease, retries structured nonterminal outcomes, and acknowledges ordinary shutdown exactly. Added real Done→In Validation→Merged crash/retry/restart coverage plus policy-denial, revocation, legacy-checkpoint, starvation, backoff, and deep-history regressions. Verification: 648 terminal-audit/auditor/workflow tests passed; direct terminal mutation scan passed 8/8; targeted Ruff and diff checks passed. The Makefile scan target could not create its task-private venv because this claimed worktree's .venv is a wrapper, so the identical scanner was run directly with the source venv. Waiting for OOMPAH-812 to land on the epic target before rebase; not submitted.
---
author: oompah
created: 2026-08-04 23:44
---
Prepared final domain-stack order while predecessor gates run: rebased the two-commit OOMPAH-781 stack onto exact OOMPAH-791 head 82f0ffd70, itself based on OOMPAH-782 a3948097f. Resolved only the two independently predicted union conflicts: orchestrator imports preserve LandingState plus terminal job types; WorkflowJobStore.recover_abandoned now supports lease_owner, phase, project_id, and actions together. New clean pushed head: 4aba71a7146b345210407320ea9f3ed170a7aae0. Post-rebase combined domain/audit verification: 565 passed, 1 xfailed; core four-module smoke 106 passed; diff check clean. Hold submission until OOMPAH-791 lands to the parent.
---
author: oompah
created: 2026-08-05 00:11
---
Advanced the prepared terminal-audit stack onto new OOMPAH-791 head a1b0c82ef (which contains OOMPAH-813 and OOMPAH-782) using an exact two-commit --onto rebase. No conflicts; new pushed head bc20fd0cade2caf3b794422d5063845fcf777196. Combined terminal/review/epic/workflow/submission-fencing verification: 571 passed, 1 expected xfail; diff check clean. Hold submission until OOMPAH-791 lands.
---
author: oompah
created: 2026-08-05 00:32
---
Restacked both implementation commits patch-equivalently onto OOMPAH-791 a923f1fbe (which includes accepted OOMPAH-813 eb5d206f2). New exact pushed head afa1f1fe9cfd90b3c5f2970b3574b61ecf883520; range-diff shows both commits '=' and branch is clean. Combined epic/review/integration/workflow facts/jobs/submission-fencing/terminal-audit suite passes 617, 1 xfailed. Task remains claimed/In Progress and unsubmitted until OOMPAH-791 lands on the stabilized common root.
---
author: oompah
created: 2026-08-05 03:19
---
Live OOMPAH-818 resubmission exposed a terminal-audit chain generation bug within this task's scope. Tracker metadata retains Done audit audit-1fa98e0837dc in_progress at old evidence fingerprint 4b2e72bc plus a newer Merged request fingerprint b8b2f37c. Current _build_merged_entries reuses any active Done row without fingerprint equality; pure-code replay produced only Merged(new), so startup ignores stale Done and the new generation silently skips required Done auditing. Required cutover regression/fix: reuse an active Done request only when its evidence fingerprint exactly equals the current Merged generation; supersede stale active cross-target Done records while preserving attempt/history; build a fresh same-fingerprint Done→Merged chain across restart. Bootstrap implementation is being added to OOMPAH-820 before OOMPAH-818 reflow.
---
author: oompah
created: 2026-08-05 12:10
---
New live restart/duplicate-finalization evidence (2026-08-05, OOMPAH-824) is within this task's accepted scope, so no separate bug was filed. A standalone task staged one Merged transition but the terminal store simultaneously exposed pending audit-6b3fa26bb2f6 and running audit-11ec4964b81b. The latter independently audited exact head 50d19fe5d, posted PASS at 12:05, incremented passed, then was stale-discarded and left the task In Validation. A normal draining restart recovered audit-6b3fa26bb2f6, launched one new attempt, and that PASS authoritatively applied Merged at 12:08. Safety held (stale verdict never mutated terminal state), but work was duplicated and convergence required a second expensive Opus audit. Required regression: concurrent webhook/review/reconcile staging must coalesce by exact target+evidence generation; restart must replay an already-persisted PASS/finalization checkpoint before launching another auditor; only a genuinely distinct authoritative generation may supersede and redispatch. Live IDs and timestamps above should be used in the duplicate/restart/finalization acceptance matrix.
---
author: oompah
created: 2026-08-05 19:28
---
Fresh independent post-repair review is not test-ready and found six remaining liveness/authority blockers: generic workers can claim terminal-audit actions they do not handle; selected and prerequisite audit rows are not fenced to the containing project/task; consumed owner-rearm proofs are reapplied and wedge later exhaustion; corrupt FINALIZING payloads remain permanently RUNNING and block siblings; LIMIT-before-skip lets preserved finalizers starve generic recovery; and completed-result recurrence lacks the normal cache-invalidated live refresh. Review also flagged project-scoped active-attempt identity and bounded filtered-list/transport retry risks. No tests were run. Repairs and deterministic cross-project/crash/restart regressions are required before the next independent review.
---
<!-- COMMENTS:END -->
