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
updated_at: '2026-07-13T05:07:31.934451Z'
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
<!-- COMMENTS:END -->
