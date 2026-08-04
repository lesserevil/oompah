---
id: OOMPAH-783
type: feature
status: Backlog
priority: 1
title: Implement the durable workflow worker and resumable external-effect saga
parent: OOMPAH-766
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:59:02.492322Z'
updated_at: '2026-08-04T13:59:02.492322Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Build the worker that consumes WorkDecision actions as jobs and executes persist intent -> lease -> revalidate -> external effect -> verify -> checkpoint -> transition request -> complete. Define idempotent action handler interfaces for tracker/Git/forge/audit work, interruption checks, heartbeats, bounded timeouts, error taxonomy, and safe recovery when an effect succeeds before acknowledgement. Required tests inject death/failure after every step, stale evidence after claim, effect-already-applied, transition-applied-before-crash, lost lease, handler timeout, and shutdown drain. Acceptance: every incomplete job resumes, supersedes, or reaches explicit action_required after restart; late workers cannot mutate a reclaimed generation.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

