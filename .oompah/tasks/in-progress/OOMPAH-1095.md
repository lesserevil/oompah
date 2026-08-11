---
id: OOMPAH-1095
type: task
status: In Progress
priority: null
title: Publish direct-owner retirement before standalone delivery authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T16:44:31.960614Z'
updated_at: '2026-08-11T16:45:14.134471Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: b5767d40-1f84-4b3b-835a-59b403777c8e
  request_fingerprint: 12f1c9a13937c9bccaeeaf80a5aacffdadae0ff9d4dea50d227cc26eac5ec01b
---
## Summary

Triggered by: OOMPAH-1085 and OOMPAH-950. Live all-enforce reproduction on 2026-08-11: accepted direct-owner submission OOMPAH-1085 completed validation_submission row 5125 and transitioned to Ready at 16:27:47. Reconciliation then created standalone_delivery row 5126 at 16:28:39 while the exact direct-owner claim was still active. The durable authority_revocation event 5127 arrived later and superseded that already-started delivery at 16:28:46 as a newer implementation event. A later snapshot eventually rebuilt delivery, but the race delayed the canonical gate and can waste gate/forge work; the same-head infrastructure retry repeated the ordering boundary. OOMPAH-950 requires atomic durable owner-to-Ready handoff but did not prevent integration materialization between status commit and exact-claim retirement. Implementation scope: persist exact claim-retirement intent before or atomically with the Ready transition; make workflow publication treat retirement-pending direct-owner facts as an ordering prerequisite rather than standalone eligibility; schedule and complete exact claim revocation first; then publish exactly one standalone/shared integration generation without blindly superseding valid newer work; recover deterministically after crash at every boundary and handle ABA replacement claims fail-closed. Required tests: barrier after Ready commit/before revocation enqueue, reconciliation in that window creates no delivery; revocation completion wakes and creates exactly one delivery; restart before/after enqueue; duplicate submit; same-head retry; ABA replacement; epic child and ordinary worker unchanged; no full gate or forge lookup starts before retirement. Acceptance: an accepted direct-owner submission hands authority to integration without a transient competing delivery, no standalone job is superseded merely because the captured owner claim is retired, delivery starts promptly after exact retirement, focused owner/workflow/integration tests and full make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

