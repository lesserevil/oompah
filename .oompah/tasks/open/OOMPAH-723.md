---
id: OOMPAH-723
type: task
status: Open
priority: null
title: Isolate maintenance-lane nonblocking test from awaited tracker I/O
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-722
labels: []
assignee: null
created_at: '2026-08-03T15:20:07.046080Z'
updated_at: '2026-08-03T16:02:51.198207Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 1a62fd0c936174e14dccadb19cc13615e82e9470e1238ece815bcf6515b01ca9
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 457cb592-c5f0-4b37-a144-f279f672f56c
  claim_owner: 2dcc53e1-cdcd-4522-a08d-de6ce4222a8c
  claimed_at: '2026-08-03T16:02:40.206154+00:00'
  claim_expires_at: '2026-08-03T16:32:40.206154+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 8020d40b-4df0-4b09-aa80-25f4b7bff628
oompah.task_costs:
  total_input_tokens: 50959
  total_output_tokens: 1011
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 50959
      output_tokens: 1011
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 50959
    output_tokens: 1011
    cost_usd: 0.0
    recorded_at: '2026-08-03T15:59:29.901977+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-723__20260803T155859Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-723
    source_sha: d510748342777dd4748070d83391ffb0eae40091
    completed_at: '2026-08-03T15:59:29.932498+00:00'
---
## Summary

Triggered by the exact-head OOMPAH-722 full gate on 2026-08-03: make test passed 15,119 tests but failed tests/test_orchestrator_handlers.py::TestMaintenanceLaneNonBlocking::test_tick_does_not_await_maintenance_heal. The test intends to prove _tick does not await _run_step5b_maintenance, but it leaves _recover_release_addendum_leases unstubbed even though the adjacent test documents that this awaited tracker scan can exceed the suite timeout under four-worker load. The result is a race/load-dependent failure unrelated to the branch under test.\n\nImplementation scope:\n- Reproduce the full-gate failure under parallel load.\n- Isolate test_tick_does_not_await_maintenance_heal from unrelated awaited tracker/filesystem work, using the same deterministic stub pattern as test_tick_starts_maintenance_future.\n- Preserve the structural invariant: _maintenance_future exists, remains pending when _tick returns, and finishes only after the explicit unblock.\n- Do not weaken the assertion into a broad wall-clock allowance.\n- Audit neighboring maintenance-lane tests for the same missing stub without broad unrelated rewrites.\n\nRequired tests:\n- Run the focused test repeatedly and the complete tests/test_orchestrator_handlers.py module serially and under the project parallel runner.\n- Run make test at the exact repair head.\n\nAcceptance criteria:\n- The test cannot fail because _recover_release_addendum_leases or other unrelated awaited I/O is slow.\n- A real regression where _tick awaits maintenance still fails deterministically.\n- No production behavior changes are required unless the focused reproduction proves _tick itself is incorrect.\n\nIn-flight workaround: OOMPAH-722's automatically dispatched CI Failure Fixer is applying the isolated repair on that task branch so its exact-head gate can continue; link the resulting commit here and retire this bug when the repair lands.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 15:32
---
The live workaround has been implemented on OOMPAH-722 at commit 3eb3235e1aab6d17ac17b3cfc655531f8b14b5a2: the nonblocking tick test now stubs _recover_release_addendum_leases and returns a concrete empty dispatch timing map, matching its sibling isolation pattern. Focused verification passed 4/4 maintenance-lane tests, 277/277 orchestrator-handler tests, 31/31 auditor-contract tests, and 4/4 ACP output-bound tests. Keep this bug as the causal record until OOMPAH-722 passes its new exact-head full gate and merges; then archive it as resolved by that commit rather than dispatching duplicate implementation.
---
author: oompah
created: 2026-08-03 15:58
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 15:58
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-03 15:59
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 51.0K in / 1.0K out [52.0K total]
- Cost: $0.0000
- Exit: normal, Duration: 39s
- Log: OOMPAH-723__20260803T155859Z.jsonl
---
author: oompah
created: 2026-08-03 16:02
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 16:02
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
