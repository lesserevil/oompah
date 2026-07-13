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
updated_at: '2026-07-13T04:43:44.410770Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 1280aa1f-79b3-47ac-bcd4-2a4f10bac8b0
---
## Summary

Read section 7 Task detail of plans/release-branch-addendums.md. Replace the task-detail Release Picks section and Add Release Picks dialog with Release addendums and an accessible Add release branches dialog. Show rows attached to the source task only: target branch, lifecycle/queue state, PR link, and blocked error; do not show child-task links. For a Merged task, fetch the release-branch catalog, render selectable available supported branches as a labelled checkbox group, precheck/disable active selections, and submit all new selections once to the approval API with an idempotency key. Add loading, stale, empty, error, focus, and Escape behavior. Tests: DOM/rendering and request-contract tests for all states, including no child-task link and refresh-to-open after success. Acceptance: selecting two branches queues two addendums with one user action.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 04:37
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 04:37
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 04:43
---
Understanding: OOMPAH-180 is not a duplicate. Searched all tasks under OOMPAH-172 epic and the full task graph. OOMPAH-181 (epic UI) is the closest sibling but covers a different page/component. OOMPAH-180 uniquely covers the task-detail UI for release addendum selection and status display.

Scope: Replace the task-detail Release Picks section and Add Release Picks dialog in oompah/templates/dashboard.html with Release addendums and an accessible Add release branches dialog. Show rows (target branch, lifecycle/queue state, PR link, blocked error) from the source task's oompah.release_addendums metadata only — no child-task links. For Merged tasks, fetch the catalog API (OOMPAH-175, Done), render checkboxes, precheck/disable active selections, submit all new selections via the approval API (OOMPAH-176). Add all required UI states. Tests required for all rendering/request-contract scenarios.

OOMPAH-176 (approval API) is in-progress; will implement against its planned contract from plans/release-branch-addendums.md section 6 and any stub code already present.
---
<!-- COMMENTS:END -->
