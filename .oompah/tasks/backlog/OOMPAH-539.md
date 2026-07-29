---
id: OOMPAH-539
type: task
status: Backlog
priority: null
title: Keep Open-task duplicate-screening board state synchronized with live workers
parent: null
children: []
blocked_by: []
labels:
- needs:frontend
- needs:backend
- needs:test
assignee: null
created_at: '2026-07-29T00:43:25.964028Z'
updated_at: '2026-07-29T00:43:28.950003Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Production observation on 2026-07-29 while OOMPAH-538 was being screened. The live /api/v1/state payload correctly reported OOMPAH-538 with work_kind=duplicate_screening and duplicate_preflight=true, but /api/v1/issues continued to serialize the same Open task as duplicate_screening.state=unchecked for roughly the active run. Near completion the inverse occurred: the board snapshot reported running after the live worker had exited and the canonical state-branch record already contained a checked no_duplicate verdict. This makes operators believe no Open tasks are being screened.\n\nImplementation scope:\n- Invalidate and refresh the issue-board snapshot when a duplicate-preflight claim is acquired, renewed/released, or completed.\n- Broadcast the refreshed canonical issue data after the tracker mutation, while retaining the separate live running-agent chip.\n- Preserve the task's Open column placement and do not optimistically mark preflight as In Progress.\n- Avoid a stale payload-before-refresh ordering that can overwrite a newer screening badge.\n\nRequired tests:\n- Claim acquisition changes an Open card from unchecked to running promptly in the issues payload/WebSocket update.\n- Completion changes running to checked (or duplicate candidate/retry) promptly and cannot regress to an older snapshot.\n- Worker state and issue summary agree through start, renewal, completion, and failure races.\n- Normal implementation optimistic movement remains unchanged. Run focused dashboard/server snapshot tests and make test.\n\nAcceptance criteria:\nDuring a live Open-task preflight, both the running-agent chip and the Open card/detail panel show screening; after exit, all surfaces show the final canonical verdict within the normal UI refresh window; no stale update can reverse the displayed lifecycle; and the task never appears In Progress solely because of screening.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

