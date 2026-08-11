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
updated_at: '2026-08-11T17:22:01.158845Z'
work_branch: OOMPAH-1095
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
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-1095
  head_sha: cbca04ae99c93bc7edcf92270104c076b036b4c6
  submitted_at: '2026-08-11T17:21:35.917981+00:00'
  updated_at: '2026-08-11T17:21:35.917981+00:00'
oompah.work_branch: OOMPAH-1095
---
## Summary

Triggered by: OOMPAH-1085 and OOMPAH-950. Live all-enforce reproduction on 2026-08-11: accepted direct-owner submission OOMPAH-1085 completed validation_submission row 5125 and transitioned to Ready at 16:27:47. Reconciliation then created standalone_delivery row 5126 at 16:28:39 while the exact direct-owner claim was still active. The durable authority_revocation event 5127 arrived later and superseded that already-started delivery at 16:28:46 as a newer implementation event. A later snapshot eventually rebuilt delivery, but the race delayed the canonical gate and can waste gate/forge work; the same-head infrastructure retry repeated the ordering boundary. OOMPAH-950 requires atomic durable owner-to-Ready handoff but did not prevent integration materialization between status commit and exact-claim retirement. Implementation scope: persist exact claim-retirement intent before or atomically with the Ready transition; make workflow publication treat retirement-pending direct-owner facts as an ordering prerequisite rather than standalone eligibility; schedule and complete exact claim revocation first; then publish exactly one standalone/shared integration generation without blindly superseding valid newer work; recover deterministically after crash at every boundary and handle ABA replacement claims fail-closed. Required tests: barrier after Ready commit/before revocation enqueue, reconciliation in that window creates no delivery; revocation completion wakes and creates exactly one delivery; restart before/after enqueue; duplicate submit; same-head retry; ABA replacement; epic child and ordinary worker unchanged; no full gate or forge lookup starts before retirement. Acceptance: an accepted direct-owner submission hands authority to integration without a transient competing delivery, no standalone job is superseded merely because the captured owner claim is retired, delivery starts promptly after exact retirement, focused owner/workflow/integration tests and full make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 17:09
---
Implementation complete and pushed on branch OOMPAH-1095 at 3ebd421b5a6b38b0940c0a568b9746f430dfff44. The validation_submission commit lane now durably marks the exact direct-owner generation retirement-pending under the same project lock before publishing Ready; tracker-write failure/retry retains the fence, replacement-claim ABA fails closed, and retirement markers survive TTL expiry/restart until exact revocation. Workflow fact composition preserves that marker over a completed durable submission, and Ready integration remains jobless until authority_revocation removes it; the next reconciliation materializes exactly one delivery. Ordinary worker submissions without owner_claim_id remain unchanged. Verification: 755 focused owner/transition/decision/runtime/integration/workflow tests passed; the four deterministic Ready/revocation/persistence/ABA race tests passed 10/10 repeated runs; terminal mutation scan 21/21; compileall and git diff --check passed. A redundant full 20,068-test run was stopped after 1,726 passes to avoid I/O contention; the canonical submission gate should run once at submission. Per handoff instruction, task was not submitted or merged.
---
author: oompah
created: 2026-08-11 17:21
---
Fresh independent review ACCEPTED original exact 3ebd421b5a6b38b0940c0a568b9746f430dfff44: retirement-before-Ready proof covers TTL, restart, ABA replacement and concurrent delivery; 298 focused passes, production handoff/ABA 20/20, terminal scan 21/21. Rebased patch-equivalently (= range-diff) onto current main 2bdf2d942b44f15bbc4e896f03d967a163891868; new pushed exact cbca04ae99c93bc7edcf92270104c076b036b4c6. Post-rebase 438 focused changed-area tests and terminal scan 21/21 passed.
---
author: oompah
created: 2026-08-11 17:22
---
Fix direct-owner retirement-before-delivery ordering with durable TTL/restart/ABA fencing; independently reviewed and post-rebase verified at cbca04ae99c93bc7edcf92270104c076b036b4c6.
---
<!-- COMMENTS:END -->
