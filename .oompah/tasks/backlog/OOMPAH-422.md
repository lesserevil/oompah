---
id: OOMPAH-422
type: bug
status: Backlog
priority: 1
title: Require actionable handoffs for Needs Human transitions
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T20:10:29.633604Z'
updated_at: '2026-07-23T20:10:29.633604Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Enforce the tracker invariant that every transition to Needs Human is followed by a final oompah comment containing actionable human instructions or one or more explicit questions. Route all orchestrator transition paths through the shared helper and reject empty/non-actionable handoffs at the tracker boundary. Add native-tracker, GitHub-tracker, and orchestration regression tests that verify the final comment is the required human handoff. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

