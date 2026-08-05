---
id: OOMPAH-819
type: bug
status: Open
priority: 1
title: Fence Ready reconciliation against stale merged-review generations
parent: OOMPAH-768
children: []
blocked_by:
- OOMPAH-820
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T03:06:28.414558Z'
updated_at: '2026-08-05T04:52:18.571827Z'
work_branch: epic-OOMPAH-768--task-OOMPAH-819
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 6ace6d18079d04a236343266e1745edd4beb5c3ae6ad187f5e609d94a3ad5cc8
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 1225b5df-7d21-41ea-99c8-bdb5d461d0bb
  claim_owner: 4d963552-8ec1-4f4b-8986-7bc16090635b
  claimed_at: '2026-08-05T04:52:15.649413+00:00'
  claim_expires_at: '2026-08-05T05:22:15.649413+00:00'
  retry_count: 1
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 4b0405b2-07ce-4023-b58b-1a6644e26eae
oompah.work_branch: epic-OOMPAH-768--task-OOMPAH-819
oompah.integration:
  version: 2
  state: working
  attempts: 0
  task_branch: epic-OOMPAH-768--task-OOMPAH-819
  base_branch: epic-OOMPAH-768
  base_sha: eb5d206f2fc040698808130b2629a997c3c9b953
  updated_at: '2026-08-05T04:48:47.187386+00:00'
---
## Summary

Live regression on 2026-08-05 while resubmitting OOMPAH-818: task branch advanced from the head merged by PR #716 to e3140b65f4958a4b7f89a1fc414bb53e88215dc4, task submit recorded the new exact integration head and moved Ready to Integrate, but standalone Ready reconciliation reused stale review_url/review_number #716, moved the task directly to In Validation, queued a Merged audit, and created no integration-queue row or exact-head quality gate. origin/main remained f1270e41 and did not contain e3140b65. This bypasses OOMPAH-697/698 protections because the task enters via Ready reconciliation rather than stale In Review reconciliation. Implementation scope: in standalone Ready/review reconciliation, bind every open/closed/merged review outcome to its exact forge review head and the current oompah.integration head generation; a merged or closed review for an older head is historical only, must be superseded/cleared without losing history, and the newer submitted head must remain/reenter the integration queue for an exact-head quality gate and fresh review. Fence tracker/review/queue mutations against concurrent resubmit, webhook, and review merge. In Validation/Merged transitions require proof that the reviewed exact submitted head landed on the target. Relevant code: Orchestrator standalone Ready reconciliation, _ensure_review_exists/_mark_task_in_review, review metadata and IntegrationQueueStore generation, TerminalTransitionCoordinator; preserve OOMPAH-697/698 legacy recovery. Required tests: exact OOMPAH-818 same-branch post-merge resubmit with stale PR metadata; merged old head plus new integration head; review payload missing head with Git containment fallback; concurrent resubmit during reconciliation; restart/webhook lag; current-head open/merged controls; assert no terminal audit, In Validation, or queue retirement before the new exact head gates and lands. Acceptance: a task branch advance after a merged review can never reuse that review to bypass the current submission generation, and OOMPAH-818 naturally flows through a new exact-head gate/review.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-05 03:08
---
Started implementation. The tracker claim is live, but the claimed /home/shedwards/.oompah/worktrees/oompah/OOMPAH-819 checkout and local OOMPAH-819 branch were absent from Git's worktree registry. I am resolving the recorded claim base and will recreate only that missing checkout before implementing the exact-head Ready reconciliation fence and race regressions.
---
author: oompah
created: 2026-08-05 03:11
---
Topology correction recorded: OOMPAH-819 remains the systemic epic-lineage task. No implementation edits were made in its recreated checkout. The same accepted fix is now being bootstrapped on standalone main-based OOMPAH-820; OOMPAH-819 depends on that deployment and will later record the patch on the epic lineage.
---
author: oompah
created: 2026-08-05 04:48
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-05 04:48
---
Run #1 [attempt=1, profile=default, role=— -> Claude/haiku]
- Turns: 0, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 16s
---
<!-- COMMENTS:END -->
