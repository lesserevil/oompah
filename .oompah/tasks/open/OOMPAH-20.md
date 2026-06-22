---
id: OOMPAH-20
type: task
status: Open
priority: 1
title: Run CI for release branches
parent: OOMPAH-17
children: []
blocked_by:
- OOMPAH-18
labels:
- release:1.0
assignee: null
created_at: '2026-06-22T01:15:01.066849Z'
updated_at: '2026-06-22T01:35:10.413496Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan: plans/oompah-1.0-release.md#epic-a-define-and-harden-the-10-release-train

WHAT TO DO
Update CI triggers so the normal quality gate runs for release/* branches and pull requests targeting release branches.

HOW TO VERIFY
The workflow configuration includes release/* branch patterns and the changed workflow can be validated through a release-branch test run or an equivalent workflow syntax check.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

