---
id: OOMPAH-537
type: task
status: In Progress
priority: null
title: Wake event-driven scheduler when a project resumes
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T00:05:46.463901Z'
updated_at: '2026-07-29T00:05:58.953166Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Production follow-up discovered while verifying OOMPAH-535 and OOMPAH-536. POST /api/v1/projects/{project_id}/resume persists paused=false, but unlike global orchestrator unpause it does not request a refresh or post a REFRESH_REQUESTED event. With event-driven scheduling, the project can remain undispatched and the dashboard snapshot can continue showing paused=true until the five-minute full-sync safety poll.\n\nImplementation scope:\n- After a successful project resume, wake the active orchestrator so it runs an immediate poll/reconciliation/dispatch cycle.\n- Preserve 404/validation behavior and project-scoped pause semantics. Do not globally unpause the orchestrator.\n- Ensure the dashboard snapshot refreshes promptly from the resulting tick.\n\nRequired tests:\n- Project resume clears the project pause and requests exactly one scheduler refresh/wake-up.\n- Unknown-project and failed updates do not request a refresh.\n- Project pause does not accidentally wake or globally change scheduler state unless explicitly intended.\n- Run focused tests and make test.\n\nAcceptance criteria:\nA resumed project becomes dispatchable without waiting for the periodic full-sync interval; the next event-driven tick sees paused=false; other project/global pause state is unchanged; and production verification can observe OOMPAH-469 dispatched under a non-duplicate implementation focus.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-29 00:05
---
Claimed directly during live verification. The project pause is already persisted as false, but no refresh event was posted, so no agent can be dispatched before this fix or the periodic full sync.
---
<!-- COMMENTS:END -->
