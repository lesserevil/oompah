---
id: OOMPAH-883
type: task
status: Open
priority: null
title: Break epic-rebase and child-integration ordering deadlocks
parent: null
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-879
labels: []
assignee: null
created_at: '2026-08-07T12:02:23.163009Z'
updated_at: '2026-08-07T12:09:05.202579Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 77f7d0fc4a05d3d41f7a69977b130dcb86eb08bfd126752c7c94d246a02e53ac
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 278a90fc-4c96-4dd5-928e-306b26f1c980
  claim_owner: 0c3fdd32-3af4-41c2-89eb-bba40d25c9aa
  claimed_at: '2026-08-07T12:07:21.454633+00:00'
  claim_expires_at: '2026-08-07T12:37:21.454633+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: a0c4c3ad-582e-4f8d-a564-dd1b535b6e8c
---
## Summary

Live regression on epic OOMPAH-763 at 2026-08-07: Ready children OOMPAH-863 and OOMPAH-866 had accepted remote heads but eligible_ready_count remained zero because their merged cross-epic prerequisite OOMPAH-845 was not reachable from the stale epic branch. OOMPAH-877, the task that would rebase that epic onto current main and make the prerequisite reachable, was conservatively fenced until those Ready children integrated. This creates a cycle: child integration waits for the rebase, while the rebase waits for child integration. The operator had to revise sequencing manually.

Implementation scope: teach the integration/rebase planner to identify tasks blocked solely because a stale epic has not yet absorbed current main; allow the one exact-generation epic rebase helper to run once other shared-branch mutation is fenced, without waiting for Ready children whose eligibility that rebase unlocks; after the rebase, re-evaluate and integrate those children normally. Preserve accepted child heads, dynamic dependency checks, exact-generation authority, and per-epic serialization. Surface a durable diagnostic when a genuine independent blocker remains rather than silently reporting eligible_ready_count=0.

Relevant code: orchestrator epic staleness/rebase scheduling, _integration_satisfied_dependencies, integration eligibility/maintenance state, and exact-generation rebase authority from OOMPAH-879.

Required tests: reproduce an epic behind main with two Ready children depending on a standalone task merged only on main; prove the rebase helper is eligible and no child is discarded; advance the epic to main and prove both children become normally integrable; cover a genuine unresolved dependency that must still block, concurrent helper fencing, restart recovery, and dynamic arrival of another accepted child.

Acceptance criteria: the scheduler cannot form a wait cycle between an epic rebase and child integrations that the rebase itself unlocks; the system chooses and records a safe ordering automatically; no accepted head or dependency invariant is bypassed; focused integration/rebase tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 12:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-07 12:08
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-08-07 12:09
---
Deeper live-code analysis shows this is not an independent planner deadlock. _detect_and_repair_integration_queue_staleness_block already recognizes a Ready child blocked by terminal work reachable from the target, schedules the epic rebase first, and re-evaluates child integration afterward. It fired in this incident by creating OOMPAH-882. The actual defect was that it failed to reuse/fence the already-authorized OOMPAH-877 helper; that exact-generation duplicate filing/admission/push race is OOMPAH-879, now including the O882 recurrence. The operator workaround revised sequencing and safely retained the single rebase. Archive this duplicate rather than implement a second overlapping fix.
---
<!-- COMMENTS:END -->
