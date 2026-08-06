---
id: OOMPAH-837
type: task
status: Done
priority: 1
title: Bind epic rollup, delivery, repair, and cleanup to durable handlers
parent: OOMPAH-804
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T16:38:45.984953Z'
updated_at: '2026-08-06T12:55:21.860415Z'
work_branch: epic-OOMPAH-804--task-OOMPAH-837
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-804--task-OOMPAH-837
  base_branch: epic-OOMPAH-804
  base_sha: ef2120815421b58172d8e034261bf7c8630bfdbd
  head_sha: ef2120815421b58172d8e034261bf7c8630bfdbd
  integrated_sha: ef2120815421b58172d8e034261bf7c8630bfdbd
  submitted_at: '2026-08-06T12:14:55.045956+00:00'
  updated_at: '2026-08-06T12:31:27.496699+00:00'
oompah.agent_run_id: null
oompah.work_branch: epic-OOMPAH-804--task-OOMPAH-837
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 449e3fded19ce20e2450944a0927e7a97f827b7dd4fdc729b1d36453a7b32ba6
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: Task state or duplicate-relevant content changed while screening was running.
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 1
  retry_after: '2026-08-06T11:52:35.037195+00:00'
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.task_costs:
  total_input_tokens: 87
  total_output_tokens: 13644
  total_cost_usd: 0.0
  by_model:
    sonnet:
      input_tokens: 12
      output_tokens: 48
      cost_usd: 0.0
    unknown:
      input_tokens: 75
      output_tokens: 13596
      cost_usd: 0.0
  runs:
  - profile: standard
    model: sonnet
    input_tokens: 12
    output_tokens: 48
    cost_usd: 0.0
    recorded_at: '2026-08-06T12:14:43.608712+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 75
    output_tokens: 13596
    cost_usd: 0.0
    recorded_at: '2026-08-06T12:55:19.235614+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-e2610ad15866: '2026-08-06T12:54:53.527726+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-837
    target_state: Done
    evidence_fingerprint: 358e445964cf16f891297391c78acff7059bbb2f1b53e4c00f5a172ec8df9f4a
    audit_ids:
    - audit-b97e164cdd4c
    kind: result
    applied: true
    retired_at: '2026-08-06T12:54:53.527733+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-837
    audit_id: audit-b97e164cdd4c
    attempt_id: attempt-e2610ad15866
    target_state: Done
    evidence_fingerprint: 358e445964cf16f891297391c78acff7059bbb2f1b53e4c00f5a172ec8df9f4a
    status: Done
    audit_ids:
    - audit-b97e164cdd4c
    applied: true
    created_at: '2026-08-06T12:54:53.527744+00:00'
    applied_at: '2026-08-06T12:55:02.371714+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b97e164cdd4c
    project_id: proj-14849f1b
    task_id: OOMPAH-837
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 358e445964cf16f891297391c78acff7059bbb2f1b53e4c00f5a172ec8df9f4a
    attempts:
    - version: 1
      attempt_id: attempt-e2610ad15866
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 358e445964cf16f891297391c78acff7059bbb2f1b53e4c00f5a172ec8df9f4a
      created_at: '2026-08-06T12:32:33.376836+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-06T12:32:33.376836+00:00'
      branch_key: epic-OOMPAH-804--task-OOMPAH-837
      verdict: pass
      completed_at: '2026-08-06T12:54:53.527604+00:00'
      ended_at: '2026-08-06T12:54:53.527604+00:00'
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-08-06T12:31:29.860837+00:00'
    updated_at: '2026-08-06T12:54:53.527604+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e2610ad15866
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 358e445964cf16f891297391c78acff7059bbb2f1b53e4c00f5a172ec8df9f4a
    created_at: '2026-08-06T12:32:33.376836+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-06T12:32:33.376836+00:00'
    branch_key: epic-OOMPAH-804--task-OOMPAH-837
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
author: oompah
created: 2026-08-06 11:48
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-06 11:48
---
Agent failed: Task worktree /home/shedwards/.oompah/worktrees/oompah/OOMPAH-837 is on OOMPAH-837, not expected branch epic-OOMPAH-804--task-OOMPAH-837; refusing to reset it. Retrying in 10s (attempt #1)
---
author: oompah
created: 2026-08-06 11:48
---
Run #1 [attempt=1, profile=standard, role=— -> Claude/sonnet]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 13s
---
author: oompah
created: 2026-08-06 11:50
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 11:50
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 18s
---
author: oompah
created: 2026-08-06 11:52
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 11:52
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 15s
---
author: oompah
created: 2026-08-06 12:12
---
Repaired the exact-gate-only async resource leak at ef2120815: removed six abandoned sleep coroutine fixtures and made both environment-dependent webhook spawn paths deterministic. Focused submission-fencing, webhook, and epic-rebase suites passed 265 serial and 265 xdist with RuntimeWarning and PytestUnraisableExceptionWarning promoted to errors; secret scan, diff check, and independent review passed.
---
author: oompah
created: 2026-08-06 12:13
---
The combined-tree quality gate failed on `epic-OOMPAH-804--task-OOMPAH-837`. Fix the failure on that private branch, run the full configured quality gate, push, and `oompah task submit` it again.

Gate output:
```
Combined-tree quality gate infrastructure_error: Trusted quality-gate runtime corruption detected; candidate CI was not run: trusted editable source mapping is inconsistent: expected one of ['/home/shedwards/src/oompah'] or immutable candidate /home/shedwards/.oompah/tmp/oompah-quality-gate-sv4ldtjn/workspace; actual /home/shedwards/.oompah/worktrees/oompah/OOMPAH-845. Repair or replace the service test runtime before rerunning the branch gate.
```
---
author: oompah
created: 2026-08-06 12:13
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-08-06 12:13
---
Focus: Refactoring Specialist
---
author: oompah
created: 2026-08-06 12:14
---
Run #1 [attempt=1, profile=standard, role=standard -> Claude/sonnet]
- Turns: 0, Tool calls: 4
- Tokens: 12 in / 48 out [60 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 8s
- Log: OOMPAH-837__20260806T121352Z.jsonl
---
author: oompah
created: 2026-08-06 12:14
---
The gate infrastructure refusal was caused by the shared .venv editable mapping being repointed by OOMPAH-845's required Make scan, not by this candidate. Restored the trusted runtime to /home/shedwards/src/oompah using make -B setup test-setup and verified oompah.__file__ resolves to the root checkout. Candidate ef2120815 is unchanged; resubmitting the exact head.
---
author: oompah
created: 2026-08-06 12:15
---
Trusted quality-gate runtime restored to the root checkout; resubmitting unchanged reviewed head ef2120815 after the infrastructure-only refusal.
---
author: oompah
created: 2026-08-06 12:31
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-06 12:32
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-06 12:32
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-06 12:55
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- branch_head: ef2120815421b58172d8e034261bf7c8630bfdbd
- origin_matches_head: true
- impl_commit: cea87246aa60c5d0520d965b25269bcb9e3de859
- epic_actions_count: 10
- backend_protocol_present: true
- handler_class_present: true
- adapter_wires_schedule_action: true
- shadow_zero_write_test_pass: true
- nested_no_parent_cycle_test_pass: true
- restart_replay_test_pass: true
- rebase_idempotency_test_pass: true
- multi_project_routing_test_pass: true
- terminal_cleanup_evidence_test_pass: true
- prior_gate_regression_now_pass: test_wrong_target_helper_is_archived_without_recovery_ref_cleanup: PASSED
- focused_totals: epic-core 140, epic-strategy 355+1xf, projects/coord/service 439, fencing/webhook/orch 504
---
author: oompah
created: 2026-08-06 12:55
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 85, Tool calls: 69
- Tokens: 75 in / 13.6K out [13.7K total]
- Cost: $0.0000
- Exit: terminated, Duration: 22m 44s
- Log: OOMPAH-837__20260806T123244Z.jsonl
---
<!-- COMMENTS:END -->
