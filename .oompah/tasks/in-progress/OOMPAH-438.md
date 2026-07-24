---
id: OOMPAH-438
type: task
status: In Progress
priority: null
title: Wake dispatch after a task becomes dispatchable
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T15:53:33.753602Z'
updated_at: '2026-07-24T15:53:34.839989Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

PATCH /api/v1/issues currently updates a task to Open but does not call orchestrator.request_refresh(), leaving newly dispatchable work idle until the long safety-net poll. Trigger a refresh after a successful transition into a dispatchable status, without waking for non-dispatchable metadata-only changes. Add API regression coverage proving an Open transition requests refresh and a non-dispatchable transition does not. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

