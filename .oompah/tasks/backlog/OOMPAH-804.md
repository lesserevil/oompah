---
id: OOMPAH-804
type: task
status: Backlog
priority: 1
title: Wire durable workflow domains into the production runtime
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T19:34:18.669662Z'
updated_at: '2026-08-04T19:34:18.669662Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Implement the final production-runtime integration for OOMPAH-768 after the domain adapters exist. Construct and lifecycle-manage the shared WorkflowFact collectors, domain controllers, WorkflowJobStore, DurableWorkflowWorker, and TaskTransitionService bindings from service startup. Route production dispatch and implementation/direct-owner claims, releases, duplicate screening, focus handoff, validation submission, worker exit, authority revocation, retries, integration delivery, terminal audit, review/CI, and epic rollup events through the durable controllers; recover and drain workers safely across restart; drive UI ownership, waiting, retry, and reason projections from the same durable decisions. Add per-domain shadow comparison before enforce cutover and disable the corresponding legacy writers/reconcilers in enforce mode without deleting rollback code (OOMPAH-794 owns final deletion). Relevant context includes oompah/orchestrator.py, server/app startup and shutdown, oompah/workflow_*.py, domain workflow modules, API/WebSocket projections, .env.example, and existing transition-service wiring. Required tests: production-like native tracker plus temporary Git/forge doubles, startup migration, crash/restart with leased and retry-wait jobs, event-order races, drain/restart, shadow parity, enforce-mode single-writer assertions, and UI/executor reason parity; run make test. Acceptance: every migrated domain is constructed and active in production, each lifecycle event has one durable owner, restart resumes rather than duplicates work, UI state derives from the same accepted decision, and enforce mode has no active legacy lifecycle writer.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

