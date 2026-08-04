---
id: OOMPAH-801
type: feature
status: Backlog
priority: 1
title: Implement TransitionIntent, transition journal, and TaskTransitionService
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T14:00:53.127556Z'
updated_at: '2026-08-04T14:00:53.127556Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Create project-scoped TransitionIntent/Outcome, append-only journal, compare-and-swap preconditions, idempotency, apply/verify, and terminal coordinator adaptation. Include expected status/version/head, actor, reason, and originating job. Test concurrent conflicts, replay, stale generation, project/actor isolation, tracker failure before/after effects, terminal staging, and restart. Acceptance: service safely supports every transition class before call-site migration.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

