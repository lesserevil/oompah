---
id: OOMPAH-218
type: task
status: In Progress
priority: null
title: Count incomplete-agent safety limit per focus
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-17T18:13:13.079649Z'
updated_at: '2026-07-17T18:15:00.679644Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Update the completed-without-closing safety limit to count consecutive normal agent sessions for the same focus rather than all sessions on a task.

A successful focus handoff must reset the count for the next focus. Preserve the existing three-session limit when the same focus repeats. Add tests covering same-focus escalation to Needs Human, a focus transition resetting the counter, and a later repeat of the new focus counting independently. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

