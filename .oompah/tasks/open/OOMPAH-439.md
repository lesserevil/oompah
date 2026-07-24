---
id: OOMPAH-439
type: task
status: Open
priority: null
title: Restrict Epic Planner routing to epics or explicit handoffs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-24T15:59:50.769146Z'
updated_at: '2026-07-24T16:00:11.093573Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Prevent keyword-rich ordinary tasks from being routed to Epic Planner. Epic Planner must be eligible only when the issue type is epic or the task has an explicit needs:epic_planner label. Preserve explicit handoffs, and reactivate the Feature Developer focus in .oompah/foci.json so feature tasks have their normal route. Add regression coverage for non-epic keyword matches, explicit handoff override, and epic routing. Run make test and deploy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

