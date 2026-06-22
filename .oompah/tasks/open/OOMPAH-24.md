---
id: OOMPAH-24
type: task
status: Open
priority: 1
title: Expand release smoke tests for project-bootstrap
parent: OOMPAH-22
children: []
blocked_by:
- OOMPAH-23
labels: []
assignee: null
created_at: '2026-06-22T01:16:43.935007Z'
updated_at: '2026-06-22T01:35:19.079819Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Plan: plans/oompah-1.0-release.md#cli-and-api-contract

WHAT TO DO
Expand packaging and release smoke tests to cover oompah project-bootstrap --help in addition to the existing root and task command smoke checks.

HOW TO VERIFY
The release packaging tests fail if project-bootstrap is missing from the installed lightweight CLI.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

