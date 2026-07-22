---
id: OOMPAH-401
type: task
status: Backlog
priority: null
title: Preserve structured Markdown descriptions in native tasks
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T05:18:51.142416Z'
updated_at: '2026-07-22T05:18:51.142416Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Prevent native Markdown task creation from storing a non-empty structured Markdown description that the tracker later parses as empty. Normalize H1/H2 headings before embedding descriptions in the Summary section, validate the resulting parsed description, and add regression tests. Repair OOMPAH-308 through OOMPAH-313 so their existing structured content remains intact and their parsed descriptions are non-empty. Acceptance: structured Markdown task creation yields a non-empty API description; blank normalized descriptions are rejected; the six affected tasks are repaired through the task API; relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

