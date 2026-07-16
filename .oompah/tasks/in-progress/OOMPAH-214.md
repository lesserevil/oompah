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
updated_at: '2026-07-16T20:53:44.916893Z'
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
<!-- COMMENTS:END -->
