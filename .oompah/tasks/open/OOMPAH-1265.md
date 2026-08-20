---
id: OOMPAH-1265
type: task
status: Open
priority: 1
title: Prove external-prerequisite lifecycle convergence and observability
parent: OOMPAH-1231
children: []
blocked_by:
- OOMPAH-1266
start_blocked_by: &id001
- OOMPAH-1263
- OOMPAH-1264
labels: []
assignee: null
created_at: '2026-08-14T02:40:21.846935Z'
updated_at: '2026-08-20T23:09:35.689381Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: oompah-1231-lifecycle-acceptance-v1
  request_fingerprint: 4f48f1f0e957c03ae28cb1f4f01e0f52c4c6c9020d902bc67d1cfb4f69389377
oompah.start_blocked_by: *id001
oompah.lifecycle_revision: 1
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: d1a591bae50708aaf359f111881a4071d274e23ddea4e3a15cbe53430d1b5800
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: dbe4a9f8be2dc0854b261e3dab59801d420ab99a687bd3614ac5113a7cf274ab:56514
  claim_owner: b0161d82-55d7-4b08-9b68-ee54b4e13c9c
  claimed_at: '2026-08-20T23:09:26.174680+00:00'
  claim_expires_at: '2026-08-20T23:39:26.174680+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 189f40f2-e934-4bf7-981f-32d6a2044edb
---
## Summary

Add production-shaped cross-component acceptance for the complete external-prerequisite lifecycle: trusted worker handoff, exact parking, zero-job authority publication, restart convergence, named dependency/operator observability, prerequisite resolution, and exactly one continuation generation. Exercise TRICKLE-123 repeated unavailable-platform handoffs, TRICKLE-132 cross-project dependency/head drift, TRICKLE-139 auxiliary repair retirement, and TRICKLE-143 structured review continuation. Verify dashboard and alerts distinguish situation-normal dependency waits from named operator action, liveness has no unexplained divergence, and old jobs cannot mutate after resolution. Update user-facing operator documentation only where a concrete resolution action exists. Required checks: focused workflow/runtime/liveness/server/UI suites, deterministic restart/race tests, terminal mutation scan, and complete Makefile gate. Acceptance: live-shaped tasks remain quiet while blocked, survive restart, resume once when truthfully resolved, and expose precise recovery evidence without generic warning floods.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-14 06:03
---
Added finish-order dependency on OOMPAH-1266 (not hard-start): lifecycle acceptance/test-only work may begin after existing OOMPAH-1264 hard-start clears, but final OOMPAH-1265 integration follows the landed late-submit authority repair because both touch server/continuation observability boundaries.
---
author: oompah
created: 2026-08-14 07:34
---
Claimed for direct implementation in /home/shedwards/src/oompah-1265 on branch OOMPAH-1265 from landed OOMPAH-1264 epic head 2ff3966dd. Oompah remains paused. Beginning production-shaped test-first lifecycle acceptance in parallel while OOMPAH-1266 completes its bounded integration-authority gate; final integration remains finish-ordered after OOMPAH-1266.
---
author: oompah
created: 2026-08-14 07:55
---
Test-first lifecycle checkpoint frozen locally at ea243c8f6 (two commits, clean). Production-shaped TRICKLE-123/132/139/143 acceptance exposed and fixed replacement-after-receipt transition fencing plus truthful 409 handoff-authority conflicts. Combined prerequisite/handoff/adapter suite passes 326 tests. Task detail now exposes exact non-secret resolution CAS fields outside the global alert surface; dashboard/detail tests pass 39 tests; concrete project-owner recovery is documented in docs/external-prerequisites.md. Final integration remains finish-ordered after OOMPAH-1266 and is not pushed/submitted.
---
author: oompah
created: 2026-08-14 08:28
---
Independent bounded review signed off exact clean head d30f77126271de8e22e8aff43a8653d6d8671afa. Post-cut prerequisite ABA fencing is enforced inside the status-write lane; structured handoffs invalidate the authoritative issue snapshot and project/projectless detail caches then refresh+broadcast on accepted and durable-conflict paths; cross-scope records are malformed/non-resolvable and UI suppresses the CLI affordance. Reviewer reran 353 focused tests with no blockers. Branch remains local/unsubmitted pending finish-order integration after OOMPAH-1266.
---
<!-- COMMENTS:END -->
