---
id: OOMPAH-898
type: task
status: In Progress
priority: 0
title: Rebase epic-OOMPAH-763 onto main
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-07T14:17:57.854034Z'
updated_at: '2026-08-07T14:27:03.021896Z'
work_branch: null
target_branch: main
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.target_branch: main
oompah.epic_rebase_target:
  version: 1
  epic_identifier: OOMPAH-763
  epic_branch: epic-OOMPAH-763
  target_branch: main
  parent_id: null
  resolution: confirmed_top_level
---
## Summary

The epic branch `epic-OOMPAH-763` is stale: it has fallen behind `main`. Rebase the branch onto `origin/main`, resolve any conflicts, and force-push with `git push --force-with-lease`.

This task was auto-filed because epic OOMPAH-763 was detected as stale. Do NOT create a new branch or PR — work directly on `epic-OOMPAH-763`.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 14:27
---
Fenced as recurrence 13 of the duplicate epic-rebase authority bug. The project is paused and a direct-owner claim prevents dispatch. Canonical recovery remains OOMPAH-877 against the protected local head; remote epic-OOMPAH-763 remains ca1c527. Do not launch or mutate the shared epic worktree. Permanent repair is tracked by OOMPAH-879 with OOMPAH-891 and OOMPAH-892.
---
<!-- COMMENTS:END -->
