---
id: OOMPAH-675
type: bug
status: In Progress
priority: 1
title: Keep the parallel pytest gate stable when workers terminate
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-01T04:59:55.163807Z'
updated_at: '2026-08-01T05:37:39.498832Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
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
  total_input_tokens: 349329
  total_output_tokens: 2219
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 349329
      output_tokens: 2219
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
<!-- COMMENTS:END -->
