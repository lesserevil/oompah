---
id: OOMPAH-994
type: bug
status: Backlog
priority: 1
title: Make API task creation durable, idempotent, and bounded
parent: OOMPAH-992
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:52:30.794441Z'
updated_at: '2026-08-10T10:52:30.794441Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Add request idempotency for API task creation and its CLI/UI callers. Reuse NativeTaskTracker create_issue_once with a durable operation marker and payload fingerprint; replaying the same key must return the same task, conflicting payloads must return 409, and cancellation or restart after acceptance must not create duplicates. Bound admission so callers receive a bounded 503 before acceptance or a durable operation response after acceptance. Add tests for cancel/replay, restart recovery, conflict, and API pool responsiveness.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

