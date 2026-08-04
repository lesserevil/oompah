---
id: OOMPAH-781
type: feature
status: In Progress
priority: 1
title: Cut terminal-audit lifecycle over to durable decisions and jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:58:59.010872Z'
updated_at: '2026-08-04T21:00:31.051522Z'
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
oompah.agent_run_id: 3daeb871-6107-458a-b8d0-91606d233f47
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-781
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-781
  base_branch: epic-OOMPAH-768
  base_sha: 08f6a8c5afdaf904daaaeb625446aaec7e961a3c
  updated_at: '2026-08-04T21:00:25.596278+00:00'
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
<!-- COMMENTS:END -->
