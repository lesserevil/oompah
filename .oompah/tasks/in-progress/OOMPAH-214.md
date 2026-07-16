---
id: OOMPAH-214
type: task
status: In Progress
priority: null
title: Resolve release-delivery merge conflicts with oompah agents
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-16T20:52:52.685623Z'
updated_at: '2026-07-16T21:03:32.117126Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: fcf297f9-659b-446f-81c4-b35a4f7c93a4
---
## Summary

When a ledger-backed main-to-release delivery encounters a merge conflict, oompah must dispatch a conflict-resolution agent in the preserved delivery worktree, have it resolve/test/commit/push the delivery branch, and then continue creating or updating the release PR. Keep the delivery attached to its original ledger record; do not create a user-visible child task for the merge. Include audit state, retry/idempotency handling, and tests. Apply this behavior to the currently blocked Trickle release/0.11 delivery.
## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-16 20:53
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-07-16 20:53
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-07-16 20:53
---
UI requirement: add a clear release-delivery status view for each target branch. It must show queued, claimed/in-progress, agent conflict-resolution in progress, blocked (with actionable error and retry), PR URL/number, CI/review state, and merged/archived outcomes. The view must update without requiring users to inspect ledger files or server logs. Include UI/API tests covering these states. This is part of the task's acceptance criteria, not a follow-up.
---
author: oompah
created: 2026-07-16 20:55
---
Understanding & Plan: I'm a Merge Conflict Resolver dispatched to unblock the Trickle release/0.11 delivery (rd_a9e8232d4f3845e49d95f075861d3ec5). The delivery is blocked in worktree at /home/shedwards/.oompah/worktrees/trickle/release-rd-f075861d3ec5-release-0.11. Two conflicts to resolve: (1) .oompah/tasks/backlog/TRICKLE-11.md deleted in main but modified in HEAD — needs to accept main's deletion since main archived it; (2) crates/trickle-client/src/overlay.rs — content conflict between both sides. After resolving, I'll commit and push the work branch so the delivery executor can proceed. I also need to implement the conflict-resolution agent dispatch feature and add tests.
---
author: oompah
created: 2026-07-16 20:55
---
Discovery: Found the blocked Trickle delivery rd_a9e8232d4f3845e49d95f075861d3ec5 in worktree /home/shedwards/.oompah/worktrees/trickle/release-rd-f075861d3ec5-release-0.11 on branch oompah/release/rd-f075861d3ec5/release-0.11. Two conflicts: (1) .oompah/tasks/backlog/TRICKLE-11.md — deleted in main (archived to .oompah/tasks/archived/TRICKLE-11.md after PR#273 merged), modified in HEAD. Fix: accept deletion via git rm. (2) crates/trickle-client/src/overlay.rs — HEAD has File Issue button tests (TRICKLE-11), main added pacing overlay tests (TRICKLE-19) in the same test section. Fix: merge both sets of tests together.
---
author: oompah
created: 2026-07-16 21:03
---
Implementation: Adding conflict-resolution agent dispatch for ledger deliveries. Changes: (1) release_delivery_store.py: new mutable field conflict_agent_task_id to track dispatched agent task (audit + idempotency); (2) orchestrator.py: new _dispatch_delivery_conflict_agents() scans all projects for blocked-with-conflict deliveries and dispatches an internal oompah task (NEEDS_REBASE + merge-conflict label, using self.tracker) for each unresolved one; (3) _dispatch_conflict_agent_for_delivery() creates the task and updates delivery.conflict_agent_task_id atomically; (4) _reconcile_release_picks_pass() now calls _dispatch_delivery_conflict_agents() after the queue pass. No child task created in the managed project. Retry/idempotency: delivery.conflict_agent_task_id guards against re-dispatch. Tests added in tests/test_release_delivery_conflict_dispatch.py.
---
<!-- COMMENTS:END -->
