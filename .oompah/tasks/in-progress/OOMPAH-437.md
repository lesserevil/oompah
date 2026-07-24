---
id: OOMPAH-437
type: task
status: In Progress
priority: null
title: Promote YOLO decomposition children after application
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T02:42:07.784157Z'
updated_at: '2026-07-24T02:42:18.784087Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

When a project has YOLO mode enabled, decomposition-generated child tasks must remain Proposed while the decomposition is being applied, then be promoted to Open only after the epic and every child have been created and linked successfully. Preserve non-YOLO behavior and idempotency on retries. Add regression coverage for successful YOLO promotion, failure/partial application (no premature promotion), and non-YOLO projects. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

