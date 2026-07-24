---
id: OOMPAH-440
type: task
status: Done
priority: null
title: Count claimed shared-epic children in branch serialization
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T16:07:22.198190Z'
updated_at: '2026-07-24T16:09:51.257128Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

The shared-epic dispatch gate documents that it serializes running and claimed children, but _epic_in_flight_count currently counts only running entries. Include claimed direct children when evaluating the parent epic branch, without changing the existing P0 bypass behavior. Add regression coverage for a claimed sibling blocking dispatch and for nonmatching claims not blocking it. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

