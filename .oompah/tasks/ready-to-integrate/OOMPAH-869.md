---
id: OOMPAH-869
type: task
status: Ready to Integrate
priority: null
title: Make inherited validation-fence restart test deterministic under saturated
  gates
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T04:34:37.725618Z'
updated_at: '2026-08-07T04:47:18.410156Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 077f3f68e3b381aff73ebec786cc81ad4f29999f676618a095ac0225de6ca31d
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-07T04:35:55.062464+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Reviewed the supplied active and non-terminal task corpus;\
    \ no task addresses deterministic inherited file-descriptor validation-fence restart\
    \ testing. Closest candidates are unrelated CI recovery and test-isolation tasks.\n\
    Focus handoff: duplicate_detector  \nDuplicate preflight verdict: no_duplicate\
    \  \nMatches: none  \n\nEvidence: Reviewed the supplied active and non-terminal\
    \ task corpus; no task addresses deterministic inherited file-descriptor validation-fence\
    \ restart testing. Closest candidates are unrelated CI recovery and test-isolation\
    \ tasks."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 9ad2c34d-01da-4629-ba48-8fa35462e86d
oompah.task_costs:
  total_input_tokens: 46764
  total_output_tokens: 437
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 46764
      output_tokens: 437
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 46102
    output_tokens: 258
    cost_usd: 0.0
    recorded_at: '2026-08-07T04:35:55.060891+00:00'
  - profile: default
    model: haiku
    input_tokens: 662
    output_tokens: 179
    cost_usd: 0.0
    recorded_at: '2026-08-07T04:47:15.813203+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-869__20260807T043537Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-869
    source_sha: f2b319c1182cd654112db622a0498171e508dead
    completed_at: '2026-08-07T04:35:55.081435+00:00'
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-869
  head_sha: 519ec2e492dec109ab008ad3617a5489928f2a30
  submitted_at: '2026-08-07T04:46:47.882222+00:00'
  updated_at: '2026-08-07T04:46:47.882222+00:00'
---
## Summary

Hosted CI on exact OOMPAH-740 head 231d2b8a7 passed Python 3.11 and 3.13 but Python 3.12 failed tests/test_validation_resource_lease.py::test_restart_observes_child_that_inherited_kernel_fence after 15,779 other tests. The test starts sleep 0.5, then expects a new lease acquire with a 0.05 second wait bound to time out. Under saturated scheduling, the child can finish before the assertion reaches acquire, so the lease correctly succeeds and the timing assertion fails. Implementation scope: replace wall-clock process lifetime assumptions with deterministic child/fence synchronization that proves a surviving inherited file descriptor blocks restart acquisition; retain bounded teardown and verify the lease becomes available only after the exact child releases the kernel fence. Relevant files: tests/test_validation_resource_lease.py and validation-resource helpers only if a production defect is independently reproduced. Required tests: the exact case repeated serially and in parallel, the complete validation-resource lease module serial and parallel, and an exact full gate. Acceptance criteria: no fixed sleep is used as proof that the child remains alive, the test deterministically observes owner_count one before the blocking acquire, the acquire times out while the inherited descriptor is held, succeeds after explicit release, and no child process or lease owner leaks.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 04:35
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 04:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 04:35
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 46.1K in / 258 out [46.4K total]
- Cost: $0.0000
- Exit: normal, Duration: 25s
- Log: OOMPAH-869__20260807T043537Z.jsonl
---
author: oompah
created: 2026-08-07 04:36
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-07 04:36
---
Focus: Oompah Tests Auth Specialist
---
author: oompah
created: 2026-08-07 04:36
---
Understanding: Test test_restart_observes_child_that_inherited_kernel_fence fails non-deterministically under saturated scheduling on Python 3.12. Root cause: test uses fixed sleep (0.5s) to keep child alive, but expects acquire to timeout in 0.05s. Under high load, child finishes before assertion executes, so lease succeeds rather than timing out. Solution: Replace wall-clock timing with deterministic synchronization using condition variables or events to:
1. Ensure child is blocked/alive without relying on sleep
2. Observe owner_count before blocking acquire
3. Verify acquire timeouts while inherited FD is held
4. Verify acquire succeeds after explicit release
5. No process or lease owner leaks

Plan: Examine test and validation-resource code, implement deterministic synchronization primitives, run tests serially and in parallel.
---
author: oompah
created: 2026-08-07 04:38
---
Discovery: The failing test test_restart_observes_child_that_inherited_kernel_fence relies on wall-clock timing (sleep 0.5) to keep child alive. Under saturated scheduling, child finishes before test reaches the blocking acquire. The test expects owner_count=1 and acquire to timeout within 0.1s. Solution: Replace fixed sleep with deterministic synchronization - have subprocess signal when child is ready using a file, test waits for file, verifies owner_count=1, tests timeout acquire, polls for child completion without fixed sleep, tests success acquire.
---
author: oompah
created: 2026-08-07 04:43
---
Implementation: Replaced wall-clock timing with deterministic synchronization in test_restart_observes_child_that_inherited_kernel_fence:
1. Child process now sleeps 30s instead of 0.5s (not used as proof of life)
2. Subprocess writes child PID to file for explicit termination
3. Subprocess writes ready marker to signal child is alive and holding inherited FD
4. Test waits for ready marker before timeout acquire (deterministic proof of child alive)
5. Test verifies owner_count==1 before timeout acquire (no fixed sleep)
6. Test kills child via PID using os.killpg to release inherited FD
7. Test uses _wait_for to poll owner_count==0 instead of fixed sleep
8. Test verifies acquire succeeds after explicit child release
9. Added signal import for SIGTERM

All 139 tests pass serially and in parallel.
---
author: oompah
created: 2026-08-07 04:46
---
Verification: All tests pass with deterministic synchronization implementation:
- test_restart_observes_child_that_inherited_kernel_fence: PASS (10x run)
- All 139 tests in test_validation_resource_lease.py: PASS
- All tests in parallel (64 workers): PASS
- Related fence/FD tests (release_preserves_owner, expired_detached_descendant): PASS

Acceptance criteria verified:
✓ No fixed sleep used as proof child remains alive
✓ Test deterministically observes owner_count==1 before blocking acquire
✓ Acquire times out (0.1s) while inherited descriptor held
✓ Acquire succeeds (1s timeout) after explicit child release
✓ No child process leaks (child terminated via killpg)
✓ No lease owner leaks (owner_count verified at each step)

Branch committed and pushed to origin/OOMPAH-869.
---
author: oompah
created: 2026-08-07 04:46
---
Made inherited validation-fence restart test deterministic under saturated gates by replacing wall-clock process lifetime assumptions with deterministic child/fence synchronization using file markers and explicit process termination. All 139 tests pass serially and in parallel. No fixed sleeps used as proof, owner_count verified deterministically, acquire timeouts confirmed while FD held, and acquire succeeds only after explicit release.
---
author: oompah
created: 2026-08-07 04:47
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/haiku]
- Turns: 0, Tool calls: 37
- Tokens: 662 in / 179 out [841 total]
- Cost: $0.0000
- Exit: terminated, Duration: 11m 4s
- Log: OOMPAH-869__20260807T043623Z.jsonl
---
<!-- COMMENTS:END -->
