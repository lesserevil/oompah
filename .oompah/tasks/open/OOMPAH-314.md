---
id: OOMPAH-314
type: bug
status: Open
priority: 1
title: Deliver only selected commits to release branches and monitor release CI
parent: null
children: []
blocked_by: []
labels:
- needs:backend
assignee: null
created_at: '2026-07-21T17:25:55.951557Z'
updated_at: '2026-07-21T17:30:24.208321Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix release delivery after PR #303 merged all of main into trickle release/0.11 despite an explicit selected-commit delivery. The queue currently calls cherry_pick_delivery with sync_source_branch=True, merging origin/main before applying source_commits. Selected delivery must apply only its immutable source_commits and must not merge the complete source branch. Add post-merge release-branch CI monitoring that creates actionable Oompah remediation work for failed release builds.\n\nTests: regression proves a selected subset cannot introduce an unselected main commit; queue integration verifies sync_source_branch is false; release CI failure fixture creates/surfaces remediation; conflict behavior remains actionable.\n\nAcceptance: no selected delivery can change a target branch except through its selected commits and required delivery metadata; release CI failure is visible/actionable in Oompah.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

