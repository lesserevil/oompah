---
id: OOMPAH-754
type: bug
status: In Progress
priority: 1
title: Inspect every integration head when repairing stale epic ancestry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:03:18.208726Z'
updated_at: '2026-08-04T11:14:01.712685Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: ed701d85181bae95116f84cc4048a1073185c1df3d41ac1e829d226da25e2378
  detector_version: duplicate-detector-v1
  verdict: no_duplicate
  checked_at: '2026-08-04T11:04:34.815606+00:00'
  matched_identifiers: []
  evidence: "Focus handoff: duplicate_detector\nDuplicate preflight verdict: no_duplicate\n\
    Matches: none\nEvidence: Closest reviewed tasks OOMPAH-162, OOMPAH-163, and OOMPAH-165\
    \ are all Archived and address different epic-branch behaviors. No active duplicate\
    \ was confirmed.\nFocus handoff: duplicate_detector  \nDuplicate preflight verdict:\
    \ no_duplicate  \nMatches: none  \n\nEvidence: Closest reviewed tasks OOMPAH-162,\
    \ OOMPAH-163, and OOMPAH-165 are all Archived and address different epic-branch\
    \ behaviors. No active duplicate was confirmed."
  claim_id: null
  claim_owner: null
  claimed_at: null
  claim_expires_at: null
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: d492709f-e4f1-4219-8cd5-ed3ded297577
oompah.task_costs:
  total_input_tokens: 47153
  total_output_tokens: 504
  total_cost_usd: 0.0
  by_model:
    haiku:
      input_tokens: 47153
      output_tokens: 504
      cost_usd: 0.0
  runs:
  - profile: default
    model: haiku
    input_tokens: 47153
    output_tokens: 504
    cost_usd: 0.0
    recorded_at: '2026-08-04T11:04:34.809015+00:00'
oompah.work_contributors:
  runs:
  - run_id: OOMPAH-754__20260804T110418Z
    provider_id: prov-52e94e83
    provider_name: Codex
    model_id: gpt-5.6-luna
    focus: duplicate_detector
    source_branch: OOMPAH-754
    source_sha: 5368e23617a98569caf7370b0f2eb63d41c8ba6b
    completed_at: '2026-08-04T11:04:34.850743+00:00'
---
## Summary

Triggered by: OOMPAH-741

Regression of OOMPAH-562 on live revision 5368e236 (which includes OOMPAH-749 as rebased commit 94dfee47). At 2026-08-04 11:00 UTC the service is healthy, unpaused, has 11 available slots, no running agents, no quality gate, no Oompah review, and 37 Ready integration rows with zero attempts and no leases. OOMPAH-741 is the only dependency-ready head reported by the issue API, but maintenance reports eligible_ready_count=0. It depends on terminal Merged OOMPAH-735; OOMPAH-735 head 0c7d9cbd is not reachable from origin/epic-OOMPAH-740, which is 0 ahead/35 behind origin/main. The queue should therefore schedule the OOMPAH-562 stale-ancestry repair. Instead, _detect_and_repair_integration_queue_staleness_block examines only ready_items[0]. Current durable queue order begins with OOMPAH-743, whose OOMPAH-741 dependency is nonterminal, so the detector returns false without inspecting OOMPAH-741 and no rebase task or repair state is created. This leaves the whole epic silently at attempts=0 indefinitely. Implementation scope: choose deterministic topological queue heads rather than raw insertion order, or scan all Ready rows whose nonterminal prerequisites do not precede them; detect terminal-but-unreachable cross-epic dependencies even when an earlier stored row is blocked on another Ready row; schedule exactly one authorized epic rebase/reconciliation; preserve cooldown, restart recovery, no direct unrelated epic-to-epic synchronization, terminal audit, and finish-order gates; and make issue/API waiting_on, maintenance eligible counts, and repair health describe the same authoritative eligibility decision. Relevant code: Orchestrator._process_integration_queues, _detect_and_repair_integration_queue_staleness_block, _integration_dependency_map, _integration_satisfied_dependencies, integration queue ordering/status presentation, and delivery-plane health. Required tests: exact OOMPAH-740 ordering with a dependent row stored before OOMPAH-741; mixed queues with nonterminal and terminal-unreachable dependencies; only-nonterminal dependencies do not file repair; one repair across repeated ticks/restart; failed repair becomes actionable; successful target rebase makes OOMPAH-741 eligible and produces a lease/attempt; status API and maintenance metrics agree. Acceptance criteria: no queue with a repairable topological head can remain attempts=0 beyond a bounded reconciliation interval because another stored row was inspected first; OOMPAH-741 enters a safe repair path and then resumes normal integration; no duplicate repair tasks or weakened dependency/ancestry checks; focused integration, staleness, delivery health, restart, and API tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 11:04
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-04 11:04
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-04 11:04
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/gpt-5.6-luna]
- Turns: 1, Tool calls: 0
- Tokens: 47.2K in / 504 out [47.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 35s
- Log: OOMPAH-754__20260804T110418Z.jsonl
---
author: oompah
created: 2026-08-04 11:05
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-08-04 11:05
---
Focus: Maintenance Engineer
---
author: oompah
created: 2026-08-04 11:05
---
UNDERSTANDING: The bug is that _detect_and_repair_integration_queue_staleness_block only inspects ready_items[0], missing repairable heads when an earlier queue item is blocked. Fix: scan all Ready items whose nonterminal prerequisites do not precede them, detect terminal-but-unreachable cross-epic dependencies, schedule exactly one repair task, and ensure API/maintenance metrics are consistent. Plan: (1) locate the detector and dependency resolution code, (2) implement topological-aware scanning, (3) add tests for mixed queue scenarios, (4) verify no regressions.
---
author: oompah
created: 2026-08-04 11:07
---
DISCOVERY: Found the bug in _detect_and_repair_integration_queue_staleness_block (oompah/orchestrator.py:10365). Current implementation checks only ready_items[0] (lines 10389-10391) and returns False if first item has no unsatisfied deps, missing repairable heads when blocked on nonterminal deps. Fix: iterate all Ready items, identify topological heads (those without nonterminal Ready predecessors), check their terminal-unreachable deps, and file repair for first eligible head.
---
author: oompah
created: 2026-08-04 11:14
---
IMPLEMENTATION: Modified _detect_and_repair_integration_queue_staleness_block to scan all Ready items instead of only ready_items[0]. Key changes: (1) Build ready_task_ids set for topological filtering, (2) iterate all Ready items identifying those with unsatisfied deps, (3) skip items whose unsatisfied deps include nonterminal items in the queue, (4) find first eligible item with terminal-unreachable deps for repair. Added test test_detector_skips_nonterminal_blocked_head_and_repairs_later_eligible verifying detector correctly skips blocked items and repairs eligible downstream heads. All 34 tests in test_parallel_epic_children.py and 20 in test_integration_queue.py pass.
---
<!-- COMMENTS:END -->
