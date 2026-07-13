---
id: OOMPAH-171
type: task
status: Backlog
priority: 2
title: Remove automatic draft-epic lifecycle
parent: OOMPAH-166
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:26:02.750063Z'
updated_at: '2026-07-13T02:26:02.750063Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Stop automatically adding the draft label whenever an epic is created. Remove the dashboard Draft Epic badge, swimlane draft badge, and Mark as Draft/Finalize controls, plus the corresponding label endpoints and client state where they are only used for epic drafting. Existing epics carrying the draft label must remain valid during rollout; provide a migration or compatibility cleanup that removes the label without changing their type, parent/child links, state, or shared-workflow behavior. Add server, tracker, and dashboard regression coverage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

