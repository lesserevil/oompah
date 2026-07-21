---
id: OOMPAH-332
type: task
status: Open
priority: 0
title: 'YOLO task-PR coherence break on oompah/468: merge-conflict recovery task missing
  or stale'
parent: null
children: []
blocked_by: []
labels:
- needs-human
- yolo-watchdog
assignee: null
created_at: '2026-07-21T21:01:56.725203Z'
updated_at: '2026-07-21T21:01:56.725203Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

PR #468 on oompah (branch `fix-release-selected-commits`) is in a state requiring `merge-conflict` recovery, but no matching open task exists.

- Reason: recovery task OOMPAH-331 is closed (state=Done) but PR still has merge-conflict condition
- Detector: D3 (task-PR coherence)
- Recovery: the YOLO orphan-recovery cache for this PR has been cleared, so the next tick will re-attempt to file the correct recovery task. If this watchdog task recurs without resolution, an operator must investigate the PR by hand.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

