---
id: OOMPAH-845
type: task
status: Ready to Integrate
priority: null
title: Stabilize restart-recovery state fencing test under saturated full gates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-06T03:38:29.127146Z'
updated_at: '2026-08-06T12:08:18.514628Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6b91b697da0af8fa9e8b0e92a7fa9d928789c9196e56be97118d858351f68fbd
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-06T03:54:28.304942+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: No active peer task matches OOMPAH-845\u2019s specific\
    \ restart-recovery state-fencing timeout and event-loop cleanup scope. Closest\
    \ reviewed tasks were terminal OOMPAH-177 (queue recovery), OOMPAH-203 (restart\
    \ behavior), and OOMPAH-235 (tracker-write recovery); all address different problems.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: No active peer task matches OOMPAH-845\u2019\
    s specific restart-recovery state-fencing timeout and event-loop cleanup scope.\
    \ Closest reviewed tasks were terminal OOMPAH-177 (queue recovery), OOMPAH-203\
    \ (restart behavior), and OOMPAH-235 (tracker-write recovery); all address different\
    \ problems."
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
  total_input_tokens: 46923
  total_output_tokens: 386
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46923
      output_tokens: 386
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46333
    output_tokens: 260
    cost_usd: 0.0
    recorded_at: '2026-08-06T03:54:28.304523+00:00'
  - profile: default
    model: haiku
    input_tokens: 590
    output_tokens: 126
    cost_usd: 0.0
    recorded_at: '2026-08-06T04:55:57.153428+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-845__20260806T035234Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-845
    source_sha: fe6257b596f79296b11dd4870a62bdbc79159d27
    completed_at: '2026-08-06T03:54:28.308433+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-845
  head_sha: 6a799a1483e213341e292d77e4dbf0ea970f6765
  submitted_at: '2026-08-06T12:08:07.511864+00:00'
  updated_at: '2026-08-06T12:08:07.511864+00:00'
---
## Summary

Regression after OOMPAH-805: OOMPAH-791 exact head c402ffe9b reached 16,193 passing tests, then tests/test_event_driven_loop.py::TestGracefulRestartShutdownEvent::test_restart_recovery_preserves_superseding_state[In Validation] failed near the end of the xdist gate. The exact parameter passes alone and passed 20/20 four-way concurrent focused reproductions at about 1.2 seconds, indicating saturated full-suite scheduling/storage/thread-pool latency against the global five-second test timeout rather than a deterministic state-fencing failure. Implementation scope: inspect Orchestrator construction, state save/load, asyncio.to_thread tracker read, and event-loop fixture cleanup for unrelated work; isolate any unrelated corpus/background work and give the bounded restart-recovery lifecycle assertion an explicit timeout only if its production-relevant async/thread transition legitimately needs loaded-gate headroom. Do not weaken production restart fencing or raise the global timeout. Relevant files: tests/test_event_driven_loop.py and production restart recovery only if a real leak/unbounded path is found. Required tests: all four superseding-state parameters, at least 20 repeated four-way focused runs, complete event-driven-loop module serial and -n 4, event-loop/thread cleanup assertions, and make test. Acceptance: the exact test remains semantically strict, never rewrites Merged/Archived/In Validation/Needs Human, clears the durable restart record once, leaves no live loop/thread work, and passes saturated exact gates deterministically.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 03:44
---
Additional focused evidence: after the minimal marker, the complete event-driven-loop module passed 60/60 with -n 4, but pytest emitted a destroyed-pending quarantine-worker task from another test in the same module. Include that event-loop cleanup leak in the systemic audit/acceptance rather than treating a warning from normal teardown as healthy. The in-flight OOMPAH-791 workaround remains scoped only to the proven restart-recovery timeout.
---
author: oompah
created: 2026-08-06 03:51
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-06 03:51
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-06 03:54
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.3K in / 260 out [46.6K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 18s
- Log: OOMPAH-845__20260806T035234Z.jsonl
---
author: oompah
created: 2026-08-06 03:55
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-06 03:55
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-06 03:55
---
**Understanding phase**: Investigating flaky test_restart_recovery_preserves_superseding_state[In Validation] that fails under saturated full-suite conditions but passes when run alone. Likely a latency/timeout issue rather than deterministic state-fencing failure. Plan: (1) Read the failing test and related fixtures; (2) Inspect Orchestrator construction, state save/load, asyncio.to_thread tracker read; (3) Check event-loop fixture cleanup for unrelated background work; (4) Add explicit timeout to restart-recovery lifecycle assertion if needed; (5) Verify with focused and saturated test runs. Will not weaken production fencing or raise global timeout.
---
author: oompah
created: 2026-08-06 04:41
---
**Discovery**: Found the issue - in _recover_restart_issues() (oompah/orchestrator.py:5175), asyncio.to_thread calls to tracker.fetch_issue_states_by_ids() and tracker.update_issue() have no explicit timeout. Under saturated test conditions with thread pool contention, these calls can be delayed significantly, hitting the 5-second pytest timeout. The test passes quickly when run alone (1.2s) but fails under -n 4 saturation due to thread scheduling delays, not actual timeout logic. Solution: Add explicit asyncio.wait_for() timeout wrapper around the asyncio.to_thread() calls to fail fast under saturation.
---
author: oompah
created: 2026-08-06 04:55
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 31
- Tokens: 590 in / 126 out [716 total]
- Cost: $0.0000
- Exit: terminated, Duration: 1h 0m 36s
- Log: OOMPAH-845__20260806T035528Z.jsonl
---
author: oompah
created: 2026-08-06 05:42
---
Prepared repair is independently static-reviewed, clean, and pushed at 530f0e1dc. It removes the unsafe production shutdown deadlines, tracks/drains scheduled retirement tasks, fences foreign callbacks before shutdown, handles owner-loop close races, and adds deterministic cross-thread stop regressions. This is a checkpoint, not submission; focused tests await the serialized lane and O763 restack.
---
author: oompah
created: 2026-08-06 11:50
---
New exact-gate evidence at canonical OOMPAH-837 head c31b8d32a on 2026-08-06: 16,631 passed and one test was failed by a PytestUnraisableExceptionWarning attributed during tests/test_epic_rebase_state.py::TestEpicTargetResolution::test_wrong_target_helper_is_archived_without_recovery_ref_cleanup. The leaked object was an asyncio BaseSubprocessTransport finalized after its loop closed; the traceback also reported coroutine 'sleep' was never awaited and unittest.mock patch lookup for _terminate. The named epic test has no subprocess/async behavior and three earlier exact gates at the same head passed, so it is a cross-test teardown leak exposed by GC under full-gate saturation, squarely within OOMPAH-845's event-loop/task/timer/async-generator/default-executor cleanup scope. Before submission, focused validation must demonstrate the O845 cleanup does not leave this class of transport/coroutine warnings, then compose the validated cleanup into the shared OOMPAH-804 head before rerunning the exact gate.
---
author: oompah
created: 2026-08-06 12:08
---
Closed every helper-owned pool/store, pending task, async generator, default executor, retry timer, and scheduled termination in the saturated restart tests. Focused validation: 98 serial and 98 xdist tests passed; the four-state restart recovery test passed 20/20 four-way xdist repetitions. Terminal mutation scan, secret scan, diff check, and independent review passed.
---
<!-- COMMENTS:END -->
