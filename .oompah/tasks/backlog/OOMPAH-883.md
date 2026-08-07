---
id: OOMPAH-883
type: task
status: Backlog
priority: null
title: Break epic-rebase and child-integration ordering deadlocks
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T12:02:23.163009Z'
updated_at: '2026-08-07T12:02:23.163009Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
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

