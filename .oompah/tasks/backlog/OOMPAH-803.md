---
id: OOMPAH-803
type: task
status: Backlog
priority: 1
title: Route API and auxiliary status writes through TaskTransitionService
parent: OOMPAH-769
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T14:01:03.399587Z'
updated_at: '2026-08-04T14:01:03.399587Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Migrate server/API/CLI handoff, stalled watchdog, audit enforcement, ACP tools, intake, projects, and auxiliary writers. Preserve authenticated-principal/owner rules and compatibility. Add AST boundary enforcement prohibiting direct production status writes outside service/adapters. Test REST/CLI, owner claims, intake, Needs Human, terminal aliases, and violations. Acceptance: every production transition is service-owned, journaled, and reason-coded.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

