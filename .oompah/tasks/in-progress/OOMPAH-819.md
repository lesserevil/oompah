---
id: OOMPAH-819
type: bug
status: In Progress
priority: 1
title: Fence Ready reconciliation against stale merged-review generations
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-05T03:06:28.414558Z'
updated_at: '2026-08-05T03:07:00.478946Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live regression on 2026-08-05 while resubmitting OOMPAH-818: task branch advanced from the head merged by PR #716 to e3140b65f4958a4b7f89a1fc414bb53e88215dc4, task submit recorded the new exact integration head and moved Ready to Integrate, but standalone Ready reconciliation reused stale review_url/review_number #716, moved the task directly to In Validation, queued a Merged audit, and created no integration-queue row or exact-head quality gate. origin/main remained f1270e41 and did not contain e3140b65. This bypasses OOMPAH-697/698 protections because the task enters via Ready reconciliation rather than stale In Review reconciliation. Implementation scope: in standalone Ready/review reconciliation, bind every open/closed/merged review outcome to its exact forge review head and the current oompah.integration head generation; a merged or closed review for an older head is historical only, must be superseded/cleared without losing history, and the newer submitted head must remain/reenter the integration queue for an exact-head quality gate and fresh review. Fence tracker/review/queue mutations against concurrent resubmit, webhook, and review merge. In Validation/Merged transitions require proof that the reviewed exact submitted head landed on the target. Relevant code: Orchestrator standalone Ready reconciliation, _ensure_review_exists/_mark_task_in_review, review metadata and IntegrationQueueStore generation, TerminalTransitionCoordinator; preserve OOMPAH-697/698 legacy recovery. Required tests: exact OOMPAH-818 same-branch post-merge resubmit with stale PR metadata; merged old head plus new integration head; review payload missing head with Git containment fallback; concurrent resubmit during reconciliation; restart/webhook lag; current-head open/merged controls; assert no terminal audit, In Validation, or queue retirement before the new exact head gates and lands. Acceptance: a task branch advance after a merged review can never reuse that review to bypass the current submission generation, and OOMPAH-818 naturally flows through a new exact-head gate/review.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

