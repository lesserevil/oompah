---
id: OOMPAH-958
type: bug
status: In Progress
priority: 1
title: Bridge durable integration workflow authority to exact queue leases
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T12:44:46.874602Z'
updated_at: '2026-08-09T12:56:18.962171Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by live durable workflow failures on OOMPAH-941, OOMPAH-943, OOMPAH-954, OOMPAH-955, and OOMPAH-956.\n\nThe ProductionIntegrationWorkflowBackend passes a ready IntegrationQueue row directly to Orchestrator._execute_integration_item, but the executor's current-authority predicate requires IntegrationQueue.owns_active_lease. Durable workflow integration_attempt jobs therefore deterministically fail before preparation with "integration authority was withdrawn before preparation": OOMPAH-941/OOMPAH-943 exhausted 5/5 even though their heads are already in the epic; OOMPAH-954/OOMPAH-956 have started consuming attempts; OOMPAH-955 is queued and at risk.\n\nImplementation scope: bridge durable workflow job authority to the legacy integration executor with an exact, bounded IntegrationQueue lease or an equivalently strong explicit workflow authority contract. Preserve project/task/branch/head, queue generation, workflow job generation, lease owner/token/deadline, replacement/expiry/ABA fencing, cancellation, heartbeat during long quality gates/integration, and exact release/cleanup on success, retry, cancellation, and exceptions. Never bypass or weaken IntegrationQueue.owns_active_lease for legacy callers. Make already-landed epic-child heads converge idempotently without rerunning unsafe effects.\n\nRequired tests: production-shaped workflow integration claim acquires exact queue authority and reaches preparation; missing/stale/expired/replaced queue or workflow lease fails closed; cancellation and exception release only the exact lease; heartbeat keeps a legitimate long effect authorized; concurrent legacy/workflow claims have one winner; restart/replay is idempotent; already-landed OOMPAH-941/OOMPAH-943-shaped rows complete from ancestry proof; retries for OOMPAH-954/OOMPAH-955/OOMPAH-956 no longer spend attempts on deterministic authority mismatch.\n\nAcceptance: durable integration_attempt jobs can never enter the executor without matching fenced queue authority; no stale or concurrent generation can mutate; focused integration-workflow/queue/executor/restart tests and required Makefile scans pass; after deployment, use supported service rearm/resubmission (no SQLite edits) to recover OOMPAH-941/OOMPAH-943 and let OOMPAH-954/OOMPAH-955/OOMPAH-956 flow naturally.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 12:56
---
Root cause confirmed and regression-tested on the newly composed epic head. Durable workflow integration deliberately keeps IntegrationQueue rows ready+unleased while its heartbeat-fenced workflow job owns effect authority; the shared executor incorrectly required the legacy queue lease both before preparation and again during candidate canonicalization. Implemented an explicit workflow-authority path that preserves exact job generation, queue generation, tracker branch/head, interruption, candidate head/base, and quality-gate owner fencing while leaving the legacy owns_active_lease path unchanged. Rebased head 9a61587fb0f904da22e1aa46e4cef0b79091e87c; 353 focused workflow/integration/executor/recovery tests pass. Independent review pending before push/submission.
---
<!-- COMMENTS:END -->
