---
id: OOMPAH-212
type: task
status: Merged
priority: null
title: Prevent duplicate native task records from appearing on the board
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-16T19:14:43.051668Z'
updated_at: '2026-07-16T19:16:47.165477Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Repair the duplicate TRICKLE-16 Open record after confirming the canonical task is Merged. Harden native task discovery so duplicate IDs cannot appear as separate board entries, and add regression coverage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-16 19:16
---
Repaired duplicate TRICKLE-16 record and added native tracker read deduplication with regression coverage.
---
<!-- COMMENTS:END -->
