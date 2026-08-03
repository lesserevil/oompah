---
id: OOMPAH-709
type: task
status: In Validation
priority: null
title: Make tick-delegation tests deterministic under parallel full-suite execution
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-02T23:17:45.073003Z'
updated_at: '2026-08-03T00:56:54.271766Z'
work_branch: OOMPAH-709
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/669
review_number: '669'
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 9b2194839796d0c3c2982593ae5669cc297262587a4dfaf3ae341b88fe23f4b9
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-02T23:18:27.132987+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: No active peer task covers tick-delegation scheduling\
    \ or `TestTickDelegation`; closest reviewed tasks OOMPAH-172 and OOMPAH-158 are\
    \ archived and address unrelated test-isolation/import issues."
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
oompah.task_costs:
  total_input_tokens: 50555
  total_output_tokens: 1152
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50525
      output_tokens: 384
      cost_usd: 0.0
    unknown:
      input_tokens: 30
      output_tokens: 768
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50525
    output_tokens: 384
    cost_usd: 0.0
    recorded_at: '2026-08-02T23:18:27.128161+00:00'
  - profile: auditor
    model: unknown
    input_tokens: 30
    output_tokens: 768
    cost_usd: 0.0
    recorded_at: '2026-08-03T00:55:33.467964+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-709__20260802T231813Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-709
    source_sha: 26ce120b9c48621161e4447866163f035b57d83a
    completed_at: '2026-08-02T23:18:27.145198+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-709
  head_sha: 234507c7c76611d5a10cf3eeec341f8773aadf34
  submitted_at: '2026-08-03T00:08:07.478804+00:00'
  updated_at: '2026-08-03T00:08:07.478804+00:00'
oompah.review_url: https://github.com/lesserevil/oompah/pull/669
oompah.review_number: '669'
oompah.work_branch: OOMPAH-709
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-03c795f5edee
    project_id: proj-14849f1b
    task_id: OOMPAH-709
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d3b6e024a73fe88f053211e0f7e43d03d6bbae9a25d741e66d6c0ef5c1e0b9b8
    attempts:
    - version: 1
      attempt_id: attempt-5cfed9c3692c
      target_state: Done
      request_state: pending
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d3b6e024a73fe88f053211e0f7e43d03d6bbae9a25d741e66d6c0ef5c1e0b9b8
      created_at: '2026-08-03T00:54:22.505540+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-03T00:54:22.505540+00:00'
      branch_key: OOMPAH-709
      failure_classification: infrastructure_error
      ended_at: '2026-08-03T00:55:34.894198+00:00'
      failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
        auditor capability policy denied a mutating or compound shell command; auditors
        cannot edit, commit, push, merge, or change state'
      next_retry_at: '2026-08-03T00:55:44.894170+00:00'
    - version: 1
      attempt_id: attempt-bf4a7d3278be
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: d3b6e024a73fe88f053211e0f7e43d03d6bbae9a25d741e66d6c0ef5c1e0b9b8
      created_at: '2026-08-03T00:56:47.383680+00:00'
      provider_id: prov-651d553c
      model: sonnet
      started_at: '2026-08-03T00:56:47.383680+00:00'
      branch_key: OOMPAH-709
      candidate_rotation_count: 1
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T00:53:05.081583+00:00'
    updated_at: '2026-08-03T00:56:47.383680+00:00'
  - version: 1
    audit_id: audit-320b7d504592
    project_id: proj-14849f1b
    task_id: OOMPAH-709
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d3b6e024a73fe88f053211e0f7e43d03d6bbae9a25d741e66d6c0ef5c1e0b9b8
    attempts: []
    requested_by:
      version: 1
      identity: lesserevil
      source: forge
    previous_state: In Review
    created_at: '2026-08-03T00:53:05.081583+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-5cfed9c3692c
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d3b6e024a73fe88f053211e0f7e43d03d6bbae9a25d741e66d6c0ef5c1e0b9b8
    created_at: '2026-08-03T00:54:22.505540+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-03T00:54:22.505540+00:00'
    branch_key: OOMPAH-709
    failure_classification: infrastructure_error
    ended_at: '2026-08-03T00:55:34.894198+00:00'
    failure_reason: 'read-only auditor exceeded the policy-denial limit (3): Error:
      auditor capability policy denied a mutating or compound shell command; auditors
      cannot edit, commit, push, merge, or change state'
    next_retry_at: '2026-08-03T00:55:44.894170+00:00'
  - version: 1
    attempt_id: attempt-bf4a7d3278be
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: d3b6e024a73fe88f053211e0f7e43d03d6bbae9a25d741e66d6c0ef5c1e0b9b8
    created_at: '2026-08-03T00:56:47.383680+00:00'
    provider_id: prov-651d553c
    model: sonnet
    started_at: '2026-08-03T00:56:47.383680+00:00'
    branch_key: OOMPAH-709
    candidate_rotation_count: 1
---
## Summary

Triggered by: OOMPAH-702 and OOMPAH-707

Production evidence on 2026-08-02: the isolated branch gate for unchanged OOMPAH-702 head c3c4698482dd2f8260758a381c8329e30f5b5ed2 passed 15,010 tests but failed tests/test_orchestrator_handlers.py::TestTickDelegation::test_tick_handler_order. Minutes earlier, OOMPAH-707 full parallel verification passed 15,020 tests but failed the adjacent TestTickDelegation::test_tick_runs_watchdog; that exact test passed immediately in a serial rerun. OOMPAH-706 full parallel make test passed the same area, showing scheduler/inter-test timing rather than either candidate implementation determines the outcome.

Implementation scope:
- Reproduce both TickDelegation failures under repeated parallel execution and identify the shared state, background maintenance, or ordering assumption that leaks between tests.
- Replace wall-clock/thread scheduling assumptions with explicit barriers or fully isolated orchestrator state.
- Ensure each test waits for the exact delegated handler completion it asserts and tears down every background future/executor.
- Preserve production tick handler order and concurrency; do not serialize the live scheduler merely to satisfy tests.

Relevant code: tests/test_orchestrator_handlers.py TestTickDelegation, oompah/orchestrator.py tick delegation/maintenance scheduling, and shared fixtures or executor teardown used by the full xdist gate.

Required tests:
- Repeated parallel runs of test_tick_handler_order and test_tick_runs_watchdog cannot fail from another worker or pending maintenance callback.
- Delayed handler scheduling is synchronized without sleeps.
- Background handler exceptions remain observable.
- Focused orchestrator tests and make test/check-secrets pass.

Acceptance criteria:
- The OOMPAH-702 and OOMPAH-707 unrelated full-gate failures cannot recur from scheduling order.
- Tests assert explicit completion and leave no live background work.
- Production scheduler semantics remain unchanged.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-02 23:18
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-02 23:18
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-02 23:18
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 50.5K in / 384 out [50.9K total]
- Cost: $0.0000
- Exit: normal, Duration: 18s
- Log: OOMPAH-709__20260802T231813Z.jsonl
---
author: oompah
created: 2026-08-02 23:18
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 23:18
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-02 23:19
---
**Understanding & Plan:**

OOMPAH-709 requires fixing non-deterministic test failures in TestTickDelegation (test_tick_handler_order and test_tick_runs_watchdog) that fail under parallel xdist execution but pass in serial reruns.

**Root cause hypothesis:** Tests have inter-test timing leaks where:
- Background handlers/futures from one test affect another
- Orchestrator state (executors, maintenance callbacks) is not fully isolated
- Tests rely on wall-clock timing instead of explicit completion barriers
- Thread scheduling assumptions fail under parallel load

**Planned approach:**
1. Explore test_orchestrator_handlers.py to understand current test structure and failure modes
2. Examine orchestrator.py tick delegation and handler scheduling logic
3. Identify shared state and background maintenance that leaks between tests
4. Replace time-based waits with explicit synchronization (events, barriers, or futures)
5. Ensure each test fully teardown all background work before returning
6. Run tests under repeated parallel execution to verify determinism

**Target:** Tests pass reliably under parallel execution without changing production scheduler behavior.
---
author: oompah
created: 2026-08-02 23:20
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-02 23:20
---
Focus: Test Engineer
---
author: oompah
created: 2026-08-02 23:20
---
Understanding: I will inspect TestTickDelegation and the orchestrator maintenance executor, reproduce both parallel-only failures, then replace timing assumptions with explicit completion/teardown synchronization while preserving production concurrency. I will verify focused tests and the required project checks before committing and submitting.
---
author: oompah
created: 2026-08-02 23:21
---
Discovery: TestTickDelegation constructs a new eight-thread _tick_pool per orchestrator, invokes _tick via asyncio.run, and several tests do not drain/shutdown fire-and-forget futures. _tick awaits watchdog but schedules step-5b/5c maintenance without awaiting; short-lived loops can leave executor work and closed-loop futures. I am reproducing the target failures and checking whether helper teardown plus explicit handler/future barriers fixes the shared scheduling leak.
---
author: oompah
created: 2026-08-02 23:26
---
Implementation: Added an autouse teardown in tests/test_orchestrator_handlers.py that drains helper-created orchestrator futures and shuts down tick/refresh executors at every test boundary. test_tick_handler_order and test_tick_runs_watchdog now use the dispatch mapping contract, stub unrelated recovery/maintenance, and await exact tick background completion; the watchdog executor test is isolated similarly.
---
author: oompah
created: 2026-08-02 23:26
---
Review finding before commit: _TEST_ORCHESTRATORS is a weakref.WeakSet, but its comment and correctness require strong reachability until fixture teardown. Once a test frame releases its local orch, refcount/GC may remove it from the WeakSet before the fixture resumes, defeating the drain and preserving this race. Use a fixture-scoped strong collection (or yield/register helper) that is always cleared, and add focused proof that cleanup still runs after the test body releases its local reference. Also ensure expected background exceptions are consumed without masking the original test, then run repeated xdist coverage.
---
author: oompah
created: 2026-08-02 23:30
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 0, Tool calls: 48
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: terminated, Duration: 10m 12s
- Log: OOMPAH-709__20260802T232035Z.jsonl
---
author: oompah
created: 2026-08-02 23:31
---
Direct project-owner repair claimed after the delegated draft expanded into production shutdown behavior and failed its own full handler-module run. I will keep this test-isolation bug scoped, repair the committed draft, verify repeated parallel execution plus the full gate, and submit the corrected head.
---
author: oompah
created: 2026-08-02 23:50
---
Direct repair complete at pushed head 0b14dec5438f6a29317c31b0341744c8c1c4e007. Root cause was deterministic: under full-suite load, the tick crossed its 2-second diagnostic threshold and the tests' invalid None dispatch-timing return failed only on that slow path. The tests now force that path, honor the mapping contract, await exact maintenance futures, consume background exceptions, and shut down each helper-owned tick pool. Production scheduler semantics are unchanged. Verification: exact regressions 2 passed; TestTickDelegation passed five consecutive 4-worker runs; full handler module 277 passed under xdist; check-secrets completed; branch clean and pushed.
---
author: oompah
created: 2026-08-02 23:50
---
Made tick-delegation tests deterministic without production scheduler changes. Forced slow telemetry reproduces the former load-only path, exact background completion is awaited, executor teardown is test-scoped, and background failures remain observable. Pushed head 0b14dec5438f6a29317c31b0341744c8c1c4e007; focused module 277 passed plus five repeated parallel delegation runs.
---
author: oompah
created: 2026-08-03 00:06
---
New live branch-gate reproduction from OOMPAH-702: TestTickDelegation::test_tick_notifies_observers failed only when full-suite load crossed the slow-tick diagnostic threshold. Its _handle_dispatch_needed AsyncMock returned None, violating the production mapping contract before _notify_observers. Extending this root-cause branch to make the observer test's dispatch result valid and force the diagnostic path deterministically.
---
author: oompah
created: 2026-08-03 00:08
---
Made tick-delegation tests deterministic under parallel full-suite load, including the live observer-notification slow-diagnostic reproduction from OOMPAH-702; five exact retries and all 277 orchestrator-handler tests pass.
---
author: oompah
created: 2026-08-03 00:43
---
Branch quality gate passed for `234507c7c76611d5a10cf3eeec341f8773aadf34` using `make test` in 396.2s. Review creation may proceed.
---
author: oompah
created: 2026-08-03 00:53
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-03 00:53
---
YOLO: merged PR #669.
---
author: oompah
created: 2026-08-03 00:54
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
author: oompah
created: 2026-08-03 00:54
---
Focus: Completion Auditor
---
author: oompah
created: 2026-08-03 00:55
---
Run #1 [attempt=1, profile=auditor, role=auditor -> Claude/opus]
- Turns: 0, Tool calls: 15
- Tokens: 30 in / 768 out [798 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1m 9s
- Log: OOMPAH-709__20260803T005429Z.jsonl
---
author: oompah
created: 2026-08-03 00:55
---
Auditor attempt was stopped after repeated policy denials; a different independent candidate will be tried.
---
author: oompah
created: 2026-08-03 00:56
---
Auditor dispatched (attempt #2, candidate: prov-651d553c/sonnet)
---
author: oompah
created: 2026-08-03 00:56
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
