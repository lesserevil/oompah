---
id: OOMPAH-157
type: bug
status: Open
priority: null
title: Add archive action to task detail UI
parent: null
children: []
blocked_by: []
labels:
- needs:frontend
assignee: null
created_at: '2026-06-24T16:39:56.675340Z'
updated_at: '2026-06-24T16:40:16.749114Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Task details in the oompah UI expose actions such as Request Changes, Override Readiness, and Promote to Backlog, but there is no visible action to intentionally archive/cancel a task. Users need a Will not do / Cancel / Archive control from the detail view so stale Proposed tasks can be closed without using the CLI.\n\nAcceptance criteria:\n- Task detail UI exposes a clear archive/cancel action for non-terminal tasks.\n- The action updates the task status to Archived through the existing task status API.\n- The UI uses clear wording such as Archive or Will not do, with confirmation if appropriate.\n- Tests cover the button rendering and the status update request.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

