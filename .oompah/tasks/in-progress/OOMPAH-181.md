---
id: OOMPAH-181
type: task
status: In Progress
priority: 2
title: Build epic release-addendum approval and snapshot UI
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-176
labels: []
assignee: null
created_at: '2026-07-13T02:36:15.200697Z'
updated_at: '2026-07-13T05:38:01.860394Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Read section 7 Epic detail of plans/release-branch-addendums.md. Add epic-specific release-addendum UI using the same supported-branch selection behavior as tasks. The API response and UI must show one addendum per selected target branch, snapshot size, included merged descendant count, status, PR link, and an expandable immutable child/commit snapshot. Do not reuse the old child-by-branch release-pick matrix or apply-all behavior. Tests: API rendering contract, merged-descendant snapshot display, no automatic inclusion of descendants merged after approval, and accessible dialog interactions. Acceptance: an operator can understand exactly which already-merged descendants an epic addendum will deliver without creating per-child backport tasks.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

