---
id: OOMPAH-173
type: task
status: In Progress
priority: 1
title: Add release-addendum schema and metadata repository
parent: OOMPAH-172
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:35:38.417683Z'
updated_at: '2026-07-13T02:54:39.585936Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Read sections 4 and 4.2 of plans/release-branch-addendums.md. Create oompah.release_addendum_schema with a typed ReleaseAddendum model, status enum (open, in_progress, in_review, blocked, merged, archived), parser/serializer, deterministic ID/work-branch helpers, and transition validation. Add a metadata repository/helper that reads and atomically replaces only oompah.release_addendums on a source task. Enforce one active addendum per target branch, immutable nonempty ordered commit snapshots, and no client-controlled execution evidence. Tests: valid round trips; malformed records; duplicate targets; illegal transitions; deterministic escaping/sanitization; and writes preserving unrelated metadata. Acceptance: no production caller is changed yet, but the module has complete unit coverage and is usable without release-pick child metadata.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

