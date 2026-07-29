---
id: OOMPAH-545
type: epic
status: Backlog
priority: 1
title: Make task dependencies finish-order constraints
parent: null
children:
- OOMPAH-546
- OOMPAH-547
- OOMPAH-548
- OOMPAH-549
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-29T16:21:51.688684Z'
updated_at: '2026-07-29T16:23:11.995416Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Goal

Change normal task dependencies from dispatch/start barriers into ordered-completion constraints, while retaining an explicit hard-start relationship for the rare work that truly cannot begin early.

Implementation scope

Introduce the Ready to Integrate lifecycle and durable integration metadata; add finish-order and hard-start dependency semantics with inheritance from parent epics and cycle validation; add a worker submission handoff that stages child work for integration instead of allowing direct Done; update all tracker adapters, status rollups, APIs, dashboard surfaces, prompts, and operator documentation. Integrate with the terminal-transition coordinator so only integrated, audited code reaches Done.

Acceptance criteria

Finish dependencies do not prevent agent dispatch, hard-start dependencies do, Ready to Integrate is visible and restart-safe, direct child Done cannot bypass submission/integration, dependency cycles fail with actionable diagnostics, all tracker backends preserve the new metadata, and focused tests plus make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

