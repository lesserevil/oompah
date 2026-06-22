---
id: OOMPAH-27
type: epic
status: In Review
priority: 0
title: Validate managed-project workflow readiness
parent: OOMPAH-16
children:
- OOMPAH-28
- OOMPAH-29
- OOMPAH-30
- OOMPAH-31
- OOMPAH-49
blocked_by: []
labels:
- merge-conflict
- epic:rebasing
assignee: null
created_at: '2026-06-22T01:16:50.891544Z'
updated_at: '2026-06-22T14:36:41.404134Z'
work_branch: epic-OOMPAH-27
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/348
review_number: '348'
merged_at: null
oompah.work_branch: epic-OOMPAH-27
oompah.target_branch: main
oompah.agent_run_id: cfb3411d-2787-4d9d-8bb0-e5b4ec44258a
oompah.review_url: https://github.com/lesserevil/oompah/pull/348
oompah.review_number: '348'
---
## Summary

Plan: plans/oompah-1.0-release.md#epic-c-validate-managed-project-workflow-readiness

WHAT TO DO
Validate that managed projects can use native .oompah markdown tasks as the source of truth, with optional GitHub Issues intake feeding proposed internal tasks.

DONE WHEN
State transitions, external issue reconciliation, decomposition boundaries, and bootstrap flows are verified for current managed projects.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 14:24
---
Review reconciliation reopened this task because it was marked In Review but no open review artifact exists.

No PR/MR for this branch was found.
Branch: `epic-OOMPAH-27`
Target branch: `main`
Unmerged commits: 4 commits
  0f61f570 OOMPAH-31: Validate project bootstrap flows across managed projects
  6d36a356 OOMPAH-30: Validate native-only decomposition boundaries
  8f49f31a OOMPAH-29: Add reconciliation audit tests for open/closed/reopened GitHub issues
  fa7ce9e6 OOMPAH-28: Add comprehensive native tracker state transition tests

Required: restore or recreate the PR/MR for this branch, then move the task back to In Review after the review exists.
---
author: oompah
created: 2026-06-22 14:25
---
Review reconciliation reopened this task because it was marked In Review but no open review artifact exists.

No PR/MR for this branch was found.
Branch: `epic-OOMPAH-27`
Target branch: `main`
Unmerged commits: 4 commits
  0f61f570 OOMPAH-31: Validate project bootstrap flows across managed projects
  6d36a356 OOMPAH-30: Validate native-only decomposition boundaries
  8f49f31a OOMPAH-29: Add reconciliation audit tests for open/closed/reopened GitHub issues
  fa7ce9e6 OOMPAH-28: Add comprehensive native tracker state transition tests

Required: restore or recreate the PR/MR for this branch, then move the task back to In Review after the review exists.
---
author: oompah
created: 2026-06-22 14:29
---
Review reconciliation reopened this task because it was marked In Review but no open review artifact exists.

No PR/MR for this branch was found.
Branch: `epic-OOMPAH-27`
Target branch: `main`
Unmerged commits: 4 commits
  0f61f570 OOMPAH-31: Validate project bootstrap flows across managed projects
  6d36a356 OOMPAH-30: Validate native-only decomposition boundaries
  8f49f31a OOMPAH-29: Add reconciliation audit tests for open/closed/reopened GitHub issues
  fa7ce9e6 OOMPAH-28: Add comprehensive native tracker state transition tests

Required: restore or recreate the PR/MR for this branch, then move the task back to In Review after the review exists.
---
author: oompah
created: 2026-06-22 14:29
---
The epic branch `epic-OOMPAH-27` is stale: it has fallen behind `main`. Rebase the branch onto `origin/main`, resolve any conflicts, and force-push with `git push --force-with-lease`.
---
author: oompah
created: 2026-06-22 14:29
---
Agent dispatched (profile: deep)
---
author: oompah
created: 2026-06-22 14:29
---
Focus: Merge Conflict Resolver
---
author: oompah
created: 2026-06-22 14:30
---
Understanding: This is a merge conflict resolution task. Branch epic-OOMPAH-27 has 4 commits ahead of main (OOMPAH-28 through OOMPAH-31: test files for state transitions, reconciliation, decomposition, and bootstrap flows). Main has advanced with task file changes only (.oompah/tasks/ files). There is no file overlap between the two sides, so the rebase should be conflict-free. Plan: fetch, rebase onto origin/main, run tests, force-push.
---
author: oompah
created: 2026-06-22 14:36
---
Verification: Rebase completed conflict-free. Branch now has 4 commits (OOMPAH-28 through OOMPAH-31) cleanly on top of origin/main. Tests: 7118 passed, 28 skipped, 0 failures. Force-pushed successfully to origin/epic-OOMPAH-27.
---
<!-- COMMENTS:END -->
