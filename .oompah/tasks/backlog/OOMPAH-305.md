---
id: OOMPAH-305
type: bug
status: Backlog
priority: 1
title: Reconcile dashboard task state with canonical state-branch records
parent: null
children: []
blocked_by: []
labels:
- needs:backend
- needs:frontend
assignee: null
created_at: '2026-07-21T16:27:55.585498Z'
updated_at: '2026-07-21T16:27:55.585498Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix the dashboard/API task-state display when it disagrees with Oompah’s canonical state branch.\n\nObserved reproduction: OOMPAH-286 is displayed as Merged in the UI even though the canonical record at oompah/state/proj-14849f1b/.oompah/tasks/backlog/OOMPAH-286.md has status=Backlog, parent=OOMPAH-285, and null work_branch, review_url, and merged_at. An unstarted epic child must never appear Merged.\n\nImplementation requirements:\n- Trace every dashboard/API task-list/detail read path and ensure native Markdown projects with state_branch_enabled read current state from the configured project state branch, not stale source-branch files, an old snapshot, or a differently keyed cache.\n- Define cache keys and invalidation around project ID, state branch, tracker revision/commit SHA, and task identifier. A state-branch checkpoint advancing must invalidate or atomically replace affected list/detail data.\n- Reconcile list, board, task-detail drawer, and task CLI responses so they report the same status, parent, branch, review URL, and merged timestamp.\n- Surface an explicit stale/unavailable tracker-state indicator rather than silently rendering obsolete state as authoritative.\n- Do not alter task state merely to repair the display.\n\nTests:\n- Regression fixture with OOMPAH-286-like data: source/main or stale cache says Merged while canonical state branch says Backlog; all UI/API views must show Backlog.\n- Verify state-branch checkpoint changes invalidate list and detail caches without a service restart.\n- Verify per-project state isolation and that an epic child with null merged_at cannot render Merged.\n- Verify degraded state-branch reads show a stale/unavailable indicator and retain no false terminal status.\n\nAcceptance criteria:\n- Dashboard, detail pane, CLI/API, and state-branch Markdown agree for every task.\n- Oompah never presents a task as Merged unless canonical tracker state records its terminal merge state.\n- Operators can distinguish fresh from stale tracker data and recover without manually editing task files.\n- All relevant tests pass through the project Makefile test target.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

