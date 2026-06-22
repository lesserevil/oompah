---
id: OOMPAH-45
type: task
status: In Progress
priority: 0
title: Rebase epic-OOMPAH-32 onto main
parent: OOMPAH-32
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-06-22T02:10:56.307786Z'
updated_at: '2026-06-22T02:13:27.061092Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: a707dcc1-98a2-4518-9061-354df0b9bdbf
---
## Summary

The epic branch `epic-OOMPAH-32` is stale: it has fallen behind `main`. Rebase the branch onto `origin/main`, resolve any conflicts, and force-push with `git push --force-with-lease`.

This task was auto-filed because epic OOMPAH-32 was detected as stale. Do NOT create a new branch or PR — work directly on `epic-OOMPAH-32`.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-22 02:11
---
Agent dispatched (profile: standard)
---
author: oompah
created: 2026-06-22 02:11
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-06-22 02:13
---
Understanding: OOMPAH-45 is a stale-epic maintenance task. I confirmed this worktree is on epic-OOMPAH-32, searched existing tasks for similar stale-rebase items, and found only prior rebase tasks for different epic branches, so this is not a duplicate. Plan: fetch origin, rebase epic-OOMPAH-32 onto origin/main, resolve conflicts, run relevant verification, force-push with lease, then close the task.
---
<!-- COMMENTS:END -->
