---
id: OOMPAH-408
type: task
status: Backlog
priority: null
title: Redispatch conflicted open PR resolver tasks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T15:25:36.632395Z'
updated_at: '2026-07-22T15:25:36.632395Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix YOLO conflict reconciliation so an open PR/MR with merge conflicts is always backed by a dispatchable Needs Rebase merge-conflict task. Repair tasks prematurely marked Merged and ensure a terminated/failed resolver is eligible for a subsequent resolver dispatch. Cover mature epic review branches and ordinary task branches with regression tests. Run make test. Acceptance criteria: conflicted open reviews #534/#537-style are reopened/requeued and dispatch candidates; clean or actually merged reviews are not changed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

