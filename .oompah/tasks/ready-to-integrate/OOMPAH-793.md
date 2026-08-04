---
id: OOMPAH-793
type: feature
status: Ready to Integrate
priority: 1
title: Cut implementation, direct-owner, handoff, and retry ownership over to durable
  jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-785
labels: []
assignee: null
created_at: '2026-08-04T13:59:21.541694Z'
updated_at: '2026-08-04T20:19:48.964953Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-793
  head_sha: ef5e8c30e0b5f9318db3b0c65a75dfc3c7811584
  submitted_at: '2026-08-04T20:19:43.006624+00:00'
  updated_at: '2026-08-04T20:19:43.006624+00:00'
---
## Summary

Migrate scheduler claim-to-worker-start, implementation generations, direct-owner leases, focus handoff, duplicate screening, worker exit, validation submission, authority revocation, and retry timers to workflow jobs and transition intents. Expected/advisory policy denials must not poison completion; late worker results must be fenced; direct owners and agents share one ownership model. Required tests: claim/start crash window, restart redispatch, owner takeover races, token/peer authorization changes, successful work plus handoff denial, incomplete sessions, branch reuse, retry expiry, and OOMPAH-732/751. Acceptance: each In Progress task has exactly one durable implementation/direct-owner disposition and no process-local authority race can strand or revert accepted work.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 20:19
---
Implementation complete and pushed at ef5e8c30e. Added the durable implementation workflow domain adapter, immutable versioned job payloads, fact/imperative event lanes with atomic ordering and supersession, shared agent/direct-owner dispositions, restart-safe verified receipts, generation/lease fencing, canonical durable retry deadlines, transition-service routing, and bounded atomic decision-scan commits. Independent race review approved with no remaining blocker. Verification: 211 related tests passed; 114 passed with four workers; terminal mutation scan passed; the 402-task home-backed scheduling scenario improved from >5s timeout to 0.56s. The exact-head full gate reached 15,734 passed, 7 skipped, 1 xfailed; two pre-existing load-sensitive tests failed outside this change and pass repeatedly focused. Filed OOMPAH-805 for deterministic event-loop/tick-metrics gate isolation. Filed OOMPAH-804 under OOMPAH-768 for final production runtime wiring after all domain adapters land.
---
author: oompah
created: 2026-08-04 20:19
---
Durable implementation, direct-owner, handoff, submission, exit, revocation, and retry workflow ownership is implemented at ef5e8c30e with restart/race coverage and independent approval.
---
<!-- COMMENTS:END -->
