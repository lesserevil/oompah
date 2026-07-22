---
id: OOMPAH-402
type: task
status: Backlog
priority: null
title: Advance focus after completed agent handoffs
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-22T05:27:02.143073Z'
updated_at: '2026-07-22T05:27:02.143073Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Fix scheduler behavior where a normally completed agent handoff is retried as unfinished and the next run re-selects the same non-implementation focus. Use task comments and/or persisted focus state to recognize completed focus handoffs, advance to the next applicable focus, and avoid retrying solely because the task remains non-terminal when the handoff records productive completion. Cover OOMPAH-339's repeated Test Engineer routing with regression tests. Acceptance: a completed handoff advances focus; a no-op completion still retries; OOMPAH-339-like implementation tasks do not loop through completed investigation/test foci; relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

