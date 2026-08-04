---
id: OOMPAH-754
type: bug
status: Open
priority: 1
title: Inspect every integration head when repairing stale epic ancestry
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T11:03:18.208726Z'
updated_at: '2026-08-04T11:04:05.128954Z'
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
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 9ef64432-de10-4981-8c2b-7f065dff79f3
  claim_owner: bb82706b-fb95-42cd-a68d-43d670f815c6
  claimed_at: '2026-08-04T11:03:52.298794+00:00'
  claim_expires_at: '2026-08-04T11:33:52.298794+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 23394bc3-5f27-46d8-bb55-a7549efea84f
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
<!-- COMMENTS:END -->
