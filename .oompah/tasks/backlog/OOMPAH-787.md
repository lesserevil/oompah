---
id: OOMPAH-787
type: task
status: Backlog
priority: 1
title: Complete shadow/enforce rollout, upgrade compatibility, and operator documentation
parent: OOMPAH-771
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:59:09.296051Z'
updated_at: '2026-08-04T13:59:09.296051Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Implement per-domain .env/.env.example rollout controls, persisted-schema migrations, startup compatibility, safe rollback before final flag retirement, canary health gates, and final enforcement/default cleanup. Update user docs for why-not-progressing, action_required alerts, recovery, SLOs, upgrade/rollback, and architecture; update plans with internal design and delete contradictory descriptions. Verify live canary and production-like soak before removing shadow/legacy flags. Acceptance: upgrade from current persisted state is automatic and restart-safe; rollback boundaries are documented/tested; final configuration has no obsolete toggles; operators no longer need manual task-state workarounds for recoverable conditions.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

