---
id: OOMPAH-804
type: task
status: Open
priority: 1
title: Wire durable workflow domains into the production runtime
parent: OOMPAH-768
children: []
blocked_by:
- OOMPAH-781
- OOMPAH-782
- OOMPAH-791
- OOMPAH-793
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T19:34:18.669662Z'
updated_at: '2026-08-04T20:23:33.044199Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 26f73b31db54d6fda10efb4c22f0e4338ae50da00232ad0c90e371520a79893b
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 293e0343-5535-4446-bdd1-047a7de9bf92
  claim_owner: f75f2e47-c230-48b7-9af8-09eea50f8e9b
  claimed_at: '2026-08-04T20:23:17.253343+00:00'
  claim_expires_at: '2026-08-04T20:53:17.253343+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 6c4de31c-49a0-44f1-9e63-48b2f843eb31
---
## Summary

Implement the final production-runtime integration for OOMPAH-768 after the domain adapters exist. Construct and lifecycle-manage the shared WorkflowFact collectors, domain controllers, WorkflowJobStore, DurableWorkflowWorker, and TaskTransitionService bindings from service startup. Route production dispatch and implementation/direct-owner claims, releases, duplicate screening, focus handoff, validation submission, worker exit, authority revocation, retries, integration delivery, terminal audit, review/CI, and epic rollup events through the durable controllers; recover and drain workers safely across restart; drive UI ownership, waiting, retry, and reason projections from the same durable decisions. Add per-domain shadow comparison before enforce cutover and disable the corresponding legacy writers/reconcilers in enforce mode without deleting rollback code (OOMPAH-794 owns final deletion). Relevant context includes oompah/orchestrator.py, server/app startup and shutdown, oompah/workflow_*.py, domain workflow modules, API/WebSocket projections, .env.example, and existing transition-service wiring. Required tests: production-like native tracker plus temporary Git/forge doubles, startup migration, crash/restart with leased and retry-wait jobs, event-order races, drain/restart, shadow parity, enforce-mode single-writer assertions, and UI/executor reason parity; run make test. Acceptance: every migrated domain is constructed and active in production, each lifecycle event has one durable owner, restart resumes rather than duplicates work, UI state derives from the same accepted decision, and enforce mode has no active legacy lifecycle writer.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

