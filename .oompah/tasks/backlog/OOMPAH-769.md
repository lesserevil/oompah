---
id: OOMPAH-769
type: epic
status: Backlog
priority: 1
title: Make one transition service the only task-status writer
parent: OOMPAH-763
children:
- OOMPAH-775
- OOMPAH-776
- OOMPAH-778
- OOMPAH-801
- OOMPAH-802
- OOMPAH-803
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:56:01.554943Z'
updated_at: '2026-08-04T14:01:04.890742Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Introduce a project-scoped TaskTransitionService that owns every task-status mutation. A TransitionIntent must include task/project identity, expected status/version, requested status, evidence generation and exact head when relevant, actor/authority, stable reason code, idempotency key, and originating workflow job. Persist an append-only transition journal and use compare-and-swap/idempotent verification so stale generations cannot overwrite newer work. Initially preserve current behavior while routing all direct update_issue status calls from orchestrator.py, server.py, watchdogs, intake, audit enforcement, tools, and auxiliary modules through the service. Adapt TerminalTransitionCoordinator behind the service without weakening terminal audits. Add an automated architectural test that rejects direct production status writes outside the service and tracker adapters. Required tests: concurrent conflicting intents, replay/idempotency, actor/project isolation, terminal staging, stale evidence, restart between journal/request/apply/verify, and compatibility for existing API/CLI transitions. Acceptance: the service and tracker adapters are the only production status writers; every applied/rejected/superseded transition is journaled with objective reason; existing safety semantics and API behavior remain intact.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

