---
id: OOMPAH-657
type: task
status: Open
priority: null
title: Run branch quality gates from immutable exact-head snapshots
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T11:06:15.542774Z'
updated_at: '2026-07-31T11:07:08.770628Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 156eeba91c00cafe17da43dbf88f58a7e3e04e766e328754b828313bb3033357
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 61d07321-b383-4fc9-958b-fa1dd54e52cf
  claim_owner: f6d86559-4e9d-42bf-ac66-416781dbb14f
  claimed_at: '2026-07-31T11:07:04.417669+00:00'
  claim_expires_at: '2026-07-31T11:37:04.417669+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 005e2645-9191-48ef-ae8e-a39a4acf1a4c
---
## Summary

Live race reproduced on OOMPAH-655 at 2026-07-31 11:03-11:06 UTC: a full gate launched for submitted head 2713e14ea continued in the task's reusable worktree after operator rejection/reopen, while the replacement implementation agent modified oompah/quality_gate.py and tests in that same worktree. Pytest therefore read a moving mixture that did not correspond to the recorded head, yet the result could still be consumed as exact-head evidence. Implementation scope: change the server-owned quality-gate/integration launch path and worktree lifecycle so every gate executes from an immutable snapshot of the recorded commit (dedicated detached worktree, archive, or equivalent), with the checked-out SHA verified before spawn; prevent task worktree reassignment/mutation from affecting an active gate; tie cancellation and process-group cleanup to the exact gate generation; and discard results when task/head/generation is no longer current. Relevant code includes oompah/quality_gate.py, integration/review orchestration, worktree allocation/cleanup, and their tests. Add deterministic barrier tests that start a gate, reopen and edit/reassign the normal task worktree, then prove the gate sees only its recorded head; cover old/new head gates overlapping, cancellation/rejection before completion, stale success never creating a review/integration, exact owned-descendant cleanup, and snapshot cleanup without pruning active evidence. Acceptance: a gate result is cryptographically/topologically attributable to one immutable commit, mutable task worktrees can never change its inputs, stale generations have no state effect, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 11:07
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 11:07
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
