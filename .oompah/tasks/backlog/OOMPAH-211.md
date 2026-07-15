---
id: OOMPAH-211
type: feature
status: Backlog
priority: 2
title: Deliver new task comments to running agents
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-15T20:52:07.206772Z'
updated_at: '2026-07-15T20:52:07.206772Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-210

When a comment is added to a task with an active agent run, deliver it into that agent's live context rather than only exposing it on a future dispatch. Define ordering, idempotency, audit logging, retry behavior, and graceful fallback for providers that cannot accept mid-run messages. Add unit and integration tests proving a running agent receives a newly posted task comment exactly once.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

