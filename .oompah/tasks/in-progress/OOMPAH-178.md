---
id: OOMPAH-178
type: task
status: In Progress
priority: 1
title: Execute queued addendums with worktrees and pull requests
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-177
labels: []
assignee: null
created_at: '2026-07-13T02:35:53.454708Z'
updated_at: '2026-07-13T05:12:44.384356Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a9fd5959-10de-4f7d-ade2-62da4bd1fe39
---
## Summary

Read section 8 of plans/release-branch-addendums.md. Extract reusable cherry-pick/push/PR operations from the release-pick child-task code so they operate on a ReleaseAddendum. Create/reuse a deterministic release worktree rooted at origin/<target_branch>, apply only the persisted commit snapshot, push the persisted oompah/release work branch, and create or reuse exactly one target-branch PR. Persist in_review, result_commits, and pr_url on success; persist blocked plus diagnostics on conflict or execution failure and preserve the conflicted worktree. Tests: correct target base and commit order; existing worktree/PR reuse; successful state/evidence updates; conflict preservation; non-conflict failure; and proof no tracker task is created. Acceptance: an open queue item can become an in_review addendum with a PR, while its source remains untouched.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 05:07
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 05:07
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 05:10
---
Understanding: OOMPAH-178 is not a duplicate. Searched all tasks in the OOMPAH-172 epic (OOMPAH-173 through OOMPAH-185). The done tasks cover schema (173), project config (174), catalog API (175), approval+snapshot (176), and queue claiming+recovery (177). OOMPAH-178 uniquely covers the execution step: cherry-pick commits into a release worktree, push the work branch, and create/reuse a target-branch PR. No other task covers this. Proceeding with implementation by reading section 8 of plans/release-branch-addendums.md and then extracting/implementing the execution logic.
---
author: oompah
created: 2026-07-13 05:12
---
Discovery: The key files are oompah/cherry_pick_pr_creator.py (existing cherry-pick/push/PR logic for BackportEntry+child Issue) and oompah/release_addendum_schema.py+queue.py (already implemented by OOMPAH-177). OOMPAH-178 requires a new oompah/release_addendum_executor.py that: (1) creates/reuses the worktree via worktree_key+work_branch based at origin/<target_branch>, (2) reuses an existing PR if present (idempotency), (3) applies cherry-pick from addendum.commits, (4) pushes the work_branch, (5) opens a PR targeting target_branch, (6) persists in_review+pr_url+result_commits via AddendumRepository.transition(), (7) on conflict: persists blocked+diagnostic+preserves worktree, posts comment on source task (not a child task), (8) never touches tracker.create_issue or update_issue on source. Tests will cover: target base/commit order, worktree+PR reuse, success state updates, conflict preservation, non-conflict failure (blocked), and proof no tracker task is created.
---
<!-- COMMENTS:END -->
