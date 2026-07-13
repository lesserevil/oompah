---
id: OOMPAH-180
type: task
status: In Progress
priority: 2
title: Build task release-addendum selection and status UI
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-174
- OOMPAH-175
- OOMPAH-176
labels: []
assignee: null
created_at: '2026-07-13T02:36:12.732590Z'
updated_at: '2026-07-13T04:35:33.152875Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Read section 7 Task detail of plans/release-branch-addendums.md. Replace the task-detail Release Picks section and Add Release Picks dialog with Release addendums and an accessible Add release branches dialog. Show rows attached to the source task only: target branch, lifecycle/queue state, PR link, and blocked error; do not show child-task links. For a Merged task, fetch the release-branch catalog, render selectable available supported branches as a labelled checkbox group, precheck/disable active selections, and submit all new selections once to the approval API with an idempotency key. Add loading, stale, empty, error, focus, and Escape behavior. Tests: DOM/rendering and request-contract tests for all states, including no child-task link and refresh-to-open after success. Acceptance: selecting two branches queues two addendums with one user action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

