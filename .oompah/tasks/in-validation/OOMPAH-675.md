---
id: OOMPAH-675
type: bug
status: In Validation
priority: 1
title: Keep the parallel pytest gate stable when workers terminate
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T04:59:55.163807Z'
updated_at: '2026-08-01T06:23:55.845255Z'
work_branch: OOMPAH-675
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/639
review_number: '639'
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 5ab5cde2ab072b5c4f07af63d1f20e0931acb6036cfa517d764ef6c88708cd73
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-01T05:11:47.902873+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \nEvidence: Searched active and terminal task records for\
    \ xdist, pytest worker termination, node-down, replacement-worker, process-group,\
    \ and parallel-gate terms. Closest matches were archived OOMPAH-219 and unrelated\
    \ active OOMPAH-281; neither covers this issue. No files or tracker state were\
    \ modified."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
oompah.agent_run_id: c80b7804-0b05-44f0-93e2-2099fcd339c5
oompah.task_costs:
  total_input_tokens: 349474
  total_output_tokens: 48445
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 349329
      output_tokens: 2219
      cost_usd: 0.0
    opus:
      input_tokens: 128
      output_tokens: 42687
      cost_usd: 0.0
    unknown:
      input_tokens: 17
      output_tokens: 3539
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 348763
    output_tokens: 2085
    cost_usd: 0.0
    recorded_at: '2026-08-01T05:11:47.900532+00:00'
  - profile: default
    model: haiku
    input_tokens: 566
    output_tokens: 134
    cost_usd: 0.0
    recorded_at: '2026-08-01T05:15:30.851060+00:00'
  - profile: deep
    model: opus
    input_tokens: 128
    output_tokens: 42687
    cost_usd: 0.0
    recorded_at: '2026-08-01T05:54:05.673778+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 17
    output_tokens: 3539
    cost_usd: 0.0
    recorded_at: '2026-08-01T06:23:45.987209+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-675__20260801T051057Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-675
    source_sha: cde6401136d6561b694b05f81f4337cd26d7a3fe
    completed_at: '2026-08-01T05:11:47.923643+00:00'
  - run_id: OOMPAH-675__20260801T052445Z
    provider_id: prov-651d553c
    provider_name: Claude
    model_id: opus
    focus: general
    source_branch: OOMPAH-675
    source_sha: d13a33d342e917c1ecb660e629a5e585724f2c11
    completed_at: '2026-08-01T05:54:05.679277+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-675
  base_branch: main
  base_sha: cde6401136d6561b694b05f81f4337cd26d7a3fe
  head_sha: d13a33d342e917c1ecb660e629a5e585724f2c11
  submitted_at: '2026-08-01T05:53:50.577959+00:00'
  updated_at: '2026-08-01T05:54:11.468861+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/639
oompah.review_number: '639'
oompah.work_branch: OOMPAH-675
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  applied_result_attempts:
    attempt-541cd6d55efe: '2026-08-01T06:23:32.905318+00:00'
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-675
    target_state: Done
    evidence_fingerprint: 34b9ef2b3b09ec3e0ba42be1cca1d6482f7dc60a317c202ffde1cfd40b5f6bfb
    audit_ids:
    - audit-1239e350baa1
    kind: result
    applied: true
    retired_at: '2026-08-01T06:23:32.905332+00:00'
  oompah.terminal_audit_result_intents:
  - project_id: proj-14849f1b
    task_id: OOMPAH-675
    audit_id: audit-1239e350baa1
    attempt_id: attempt-541cd6d55efe
    target_state: Done
    evidence_fingerprint: 34b9ef2b3b09ec3e0ba42be1cca1d6482f7dc60a317c202ffde1cfd40b5f6bfb
    status: In Validation
    audit_ids:
    - audit-1239e350baa1
    applied: true
    created_at: '2026-08-01T06:23:32.905352+00:00'
    applied_at: '2026-08-01T06:23:36.077269+00:00'
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-1239e350baa1
    project_id: proj-14849f1b
    task_id: OOMPAH-675
    target_state: Done
    request_state: completed
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 34b9ef2b3b09ec3e0ba42be1cca1d6482f7dc60a317c202ffde1cfd40b5f6bfb
    attempts:
    - version: 1
      attempt_id: attempt-541cd6d55efe
      target_state: Done
      request_state: completed
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 34b9ef2b3b09ec3e0ba42be1cca1d6482f7dc60a317c202ffde1cfd40b5f6bfb
      created_at: '2026-08-01T06:21:56.795217+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-01T06:21:56.795217+00:00'
      branch_key: OOMPAH-675
      verdict: pass
      completed_at: '2026-08-01T06:23:32.905127+00:00'
      ended_at: '2026-08-01T06:23:32.905127+00:00'
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T06:20:49.253937+00:00'
    updated_at: '2026-08-01T06:23:32.905127+00:00'
  - version: 1
    audit_id: audit-4b7b622193d1
    project_id: proj-14849f1b
    task_id: OOMPAH-675
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 34b9ef2b3b09ec3e0ba42be1cca1d6482f7dc60a317c202ffde1cfd40b5f6bfb
    attempts:
    - version: 1
      attempt_id: attempt-084f7ac8d3a7
      target_state: Merged
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 34b9ef2b3b09ec3e0ba42be1cca1d6482f7dc60a317c202ffde1cfd40b5f6bfb
      created_at: '2026-08-01T06:23:51.239502+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-01T06:23:51.239502+00:00'
      branch_key: OOMPAH-675
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-01T06:20:49.253937+00:00'
    updated_at: '2026-08-01T06:23:51.239502+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-541cd6d55efe
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 34b9ef2b3b09ec3e0ba42be1cca1d6482f7dc60a317c202ffde1cfd40b5f6bfb
    created_at: '2026-08-01T06:21:56.795217+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-01T06:21:56.795217+00:00'
    branch_key: OOMPAH-675
  - version: 1
    attempt_id: attempt-084f7ac8d3a7
    target_state: Merged
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 34b9ef2b3b09ec3e0ba42be1cca1d6482f7dc60a317c202ffde1cfd40b5f6bfb
    created_at: '2026-08-01T06:23:51.239502+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-01T06:23:51.239502+00:00'
    branch_key: OOMPAH-675
---
## Summary

Discovered while validating OOMPAH-674 on 2026-08-01. Two consecutive make test runs with the configured four xdist workers aborted after workers reported node down: Not properly terminated; xdist created replacement workers and LoadGroupScheduling then crashed with KeyError for WorkerController gw6. Runs stopped near 47 percent with roughly 6,956 tests passed, so the controller did not preserve actionable identities for the original failures. Focused one-worker selections pass. Implementation scope: reproduce and identify why bounded tests terminate xdist workers, ensure lifecycle or process-group tests cannot kill their pytest worker, and make the gate surface original test failures without scheduler-internal replacement crashes. Relevant areas: Makefile test target, scripts/run-tests.sh, pytest timeout and xdist configuration, process lifecycle tests. Acceptance criteria: repeated configured four-worker gates complete without lost workers or xdist internal errors; intentional timeouts report the responsible test; isolation guarantees remain intact; regression coverage exercises worker failure and replacement behavior where practical.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-01 05:10
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-01 05:10
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-01 05:11
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 7
- Tokens: 348.8K in / 2.1K out [350.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 54s
- Log: OOMPAH-675__20260801T051057Z.jsonl
---
author: oompah
created: 2026-08-01 05:12
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 05:12
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-01 05:12
---
**Understanding**: OOMPAH-675 is a stability issue where parallel pytest runs with 4 xdist workers fail when tests terminate workers, causing LoadGroupScheduling crashes (KeyError for WorkerController). Tests abort at ~47%, losing original failures.

**Planned approach**:
1. Explore Makefile test target, run-tests.sh, and pytest/xdist configuration
2. Identify which tests or test patterns terminate workers
3. Reproduce the issue with multi-worker runs
4. Implement isolation fixes to prevent tests from killing their pytest worker
5. Ensure timeout handling surfaces original test failures
6. Add regression tests for worker failure scenarios

**Scope**: Makefile, run-tests.sh, pytest.ini/conftest, process lifecycle tests
---
author: oompah
created: 2026-08-01 05:14
---
**Discovery**: Reviewed pytest configuration and worker isolation:

- pytest configured with 5s timeout using thread method (pyproject.toml)
- Worker isolation plugin (_pytest_worker_isolation.py) gives each xdist worker isolated HOME/TMPDIR/cache
- Process-global tests (test_agent.py, test_granian_*.py, test_makefile_restart_wait.py) marked with xdist_group to serialize
- Issue: Some tests may be inadvertently killing their pytest worker process via:
  1. Signals (SIGTERM/SIGKILL) affecting parent pytest process
  2. Timeouts killing the entire pytest worker thread instead of just the test
  3. Process group termination without proper identity verification

**Key files**:
- Makefile (test target with PYTEST_WORKERS=4, --dist loadgroup)
- scripts/run-tests.sh (pytest invocation)
- pyproject.toml (timeout=5, timeout_method=thread)
- tests/pytest_worker_isolation.py (per-worker filesystem isolation)
- tests/process_lifecycle.py (process lifecycle management helpers)

**Next**: Will reproduce the issue with 4-worker run and identify which test terminates workers.
---
author: oompah
created: 2026-08-01 05:15
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 34
- Tokens: 566 in / 134 out [700 total]
- Cost: $0.0000
- Exit: terminated, Duration: 3m 25s
- Log: OOMPAH-675__20260801T051209Z.jsonl
---
author: oompah
created: 2026-08-01 05:16
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-01 05:16
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-01 05:17
---
Understanding: I will trace the pytest/xdist runner and process-lifecycle tests, reproduce or isolate the four-worker worker-loss failure, then implement process/timeout isolation with regression coverage and verify focused suites before submitting.
---
author: oompah
created: 2026-08-01 05:24
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 38
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 7m 31s
- Log: OOMPAH-675__20260801T051655Z.jsonl
---
author: oompah
created: 2026-08-01 05:24
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-08-01 05:24
---
Focus: Software Engineer
---
author: oompah
created: 2026-08-01 05:29
---
**Understanding & continuation plan**: Previous runs (Codex/Haiku) reviewed pyproject/pytest_worker_isolation.py and process_lifecycle.py but did not commit code. Current pytest is 9.0.2 with pytest-xdist 3.8.0, timeout=5s thread method, --dist loadgroup, PYTEST_WORKERS=4.

Confirmed root-cause hypothesis: 'Not properly terminated' means an xdist worker's execnet channel closes without a clean shutdown message. That triggers _clone_node in dsession.py, which spawns a replacement (gw4, gw5, gw6…). LoadScopeScheduling.remove_node/schedule() does not KeyError-guard every edge case with replacement nodes (assertion 'node not in self.assigned_work' in add_node and unguarded pop in remove_node). Additionally, xdist worker_workerfinished calls sched.remove_node(node) without try/except; if a replacement gets scheduled and then finishes cleanly while assigned_work has drifted, it KeyErrors out.

Plan:
1. Reproduce with 4-worker run and identify the test(s) causing worker loss.
2. Fix the offending test(s) so a bounded test cannot terminate its own worker.
3. Configure the runner so worker-loss no longer propagates as an internal-error crash (max-worker-restart bound + preferring worksteal for non-group tests, or --tx retention).
4. Add regression coverage that exercises worker failure/replacement paths.
---
author: oompah
created: 2026-08-01 05:37
---
**Discovery — root cause identified**: pyproject.toml sets \`timeout_method = "thread"\`. pytest-timeout's timer thread calls \`os._exit(1)\` on timeout (site-packages/pytest_timeout.py:542), which terminates the xdist worker process before it can send a clean shutdown message. The xdist controller reports 'Not properly terminated', spawns a replacement worker, and LoadScopeScheduling / LoadGroupScheduling can KeyError when late worker-report events arrive for the replaced WorkerController (loadscope.py:249 mark_test_complete, worker_workerfinished remove_node path).

**Implementation**:
1. pyproject.toml: timeout_method 'thread' → 'signal'. Signal-based timeout raises pytest.Failed inside the worker's main thread, keeping the worker alive.
2. scripts/run-tests.sh: added --max-worker-restart=0 to the parallel invocation. With signal timeouts, worker loss now indicates a genuine crash and we fail fast on it — that path handles crashitem cleanly in xdist and avoids the LoadScopeScheduling replacement KeyError entirely.
3. tests/test_pytest_timeout_config.py: updated regression to assert signal method.
4. tests/test_pytest_parallel.py: added regression that the runner has --max-worker-restart=0 with loadgroup.
5. tests/test_pytest_worker_survives_timeout.py: new subprocess-driven coverage that runs pytest+xdist with a slow test and asserts (a) responsible test is named in the failure, (b) worker survives to run neighbouring tests, (c) 'Not properly terminated' / 'replacing crashed worker' / 'INTERNALERROR' never appear, (d) a genuine os._exit(1) crash is reported with --max-worker-restart=0 without a scheduler replacement crash.
---
author: oompah
created: 2026-08-01 05:53
---
**Verification**: Ran the full parallel gate twice through scripts/run-tests.sh (OOMPAH_PYTEST_WORKERS=4, 388s and 387s).

Run 1: 14737 passed, 7 skipped, 1 xfailed, 0 failed. No 'Not properly terminated', no 'replacing crashed worker', no INTERNALERROR.
Run 2: 14736 passed, 7 skipped, 1 xfailed, 1 failed. The single failure was tests/test_orchestrator_handlers.py::TestMaintenanceLaneNonBlocking::test_tick_does_not_await_maintenance_heal — a preexisting flake previously stabilized under OOMPAH-670/OOMPAH-589 (asyncio.wait_for latency race). It passes in isolation and in the whole test_orchestrator_handlers.py module (277 tests, 55s). Not related to OOMPAH-675 — the responsible test was surfaced by name (which is exactly the property this task requires). Notably, the pre-fix behaviour would have killed the worker via os._exit(1) from pytest-timeout's thread mode and lost the identity entirely.

Focused sanity: tests/test_pytest_worker_survives_timeout.py (3 new subprocess-driven tests), tests/test_pytest_timeout_config.py, tests/test_pytest_parallel.py, tests/test_agent.py, tests/test_lifespan_abort.py, tests/test_granian_bootstrap.py, tests/test_granian_e2e.py, tests/test_granian_parity.py, tests/test_makefile_restart_wait.py, tests/test_lifecycle_cli_sync_integration.py, tests/test_checkpoint_coalescing.py, tests/test_task_cost_telemetry.py, tests/test_api_agent_budget.py — all pass.

**Completion**: Delivered pyproject.toml timeout_method='signal', scripts/run-tests.sh --max-worker-restart=0, updated tests/test_pytest_timeout_config.py assertion, added tests/test_pytest_parallel.py runner assertion, and new tests/test_pytest_worker_survives_timeout.py subprocess coverage. Pushed as commit d13a33d34 to origin/OOMPAH-675.
---
author: oompah
created: 2026-08-01 05:53
---
Switched pyproject timeout_method from thread to signal so intentional per-test timeouts raise pytest.Failed in the worker's main thread instead of pytest-timeout calling os._exit(1). Added --max-worker-restart=0 to scripts/run-tests.sh so a genuine crash fails fast with the crashitem identified rather than triggering LoadScopeScheduling / LoadGroupScheduling replacement KeyError. Updated the pyproject regression and runner regression, and added tests/test_pytest_worker_survives_timeout.py — a subprocess-driven pytest+xdist run that proves signal-mode timeouts name the responsible test, neighbouring tests survive, and a hard os._exit(1) crash under --max-worker-restart=0 surfaces the crashitem without a scheduler internal error. Two full 4-worker gates completed without 'Not properly terminated' or xdist internal errors.
---
author: oompah
created: 2026-08-01 05:54
---
Agent completed successfully in 1765s (42815 tokens)
---
author: oompah
created: 2026-08-01 05:54
---
Run #2 [attempt=2, profile=deep, role=deep -> Claude/opus]
- Turns: 174, Tool calls: 122
- Tokens: 128 in / 42.7K out [42.8K total]
- Cost: $0.0000
- Exit: normal, Duration: 29m 25s
- Log: OOMPAH-675__20260801T052445Z.jsonl
---
author: oompah
created: 2026-08-01 06:12
---
Branch quality gate passed for `d13a33d342e917c1ecb660e629a5e585724f2c11` using `make test` in 386.7s. Review creation may proceed.
---
author: oompah
created: 2026-08-01 06:20
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-01 06:20
---
YOLO: merged PR #639.
---
author: oompah
created: 2026-08-01 06:21
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-01 06:22
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-01 06:23
---
Audit PASS — Done

[REDACTED]

Safe evidence:
- head_commit: d13a33d342e917c1ecb660e629a5e585724f2c11
- pyproject_timeout_method: signal (line 139)
- run_tests_sh_max_worker_restart: --max-worker-restart=0 (line 92)
- test_pytest_timeout_config_result: 2/2 passed
- test_pytest_parallel_result: 15/15 passed
- test_pytest_worker_survives_timeout_result: 3/3 passed
- full_gate_comment: 14737 passed, 7 skipped, 1 xfailed, 0 failed; no xdist errors
- pr_merged: PR #639 merged per task comment 2026-08-01 06:20
---
author: oompah
created: 2026-08-01 06:23
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/sonnet]
- Turns: 32, Tool calls: 24
- Tokens: 17 in / 3.5K out [3.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 1m 48s
- Log: OOMPAH-675__20260801T062202Z.jsonl
---
author: oompah
created: 2026-08-01 06:23
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-01 06:23
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
