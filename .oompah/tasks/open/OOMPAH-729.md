---
id: OOMPAH-729
type: bug
status: Open
priority: 1
title: Rearm terminal audit after evidence-only remediation on the same head
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-03T16:23:52.854950Z'
updated_at: '2026-08-03T16:24:25.390820Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 47992fd656f08c8452820e2fdc13ebbee52ed2bbb24cb99c6969456badd42a6f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 8fdaab9b-b974-45c9-b7f4-b0fea2246eb1
  claim_owner: 2dcc53e1-cdcd-4522-a08d-de6ce4222a8c
  claimed_at: '2026-08-03T16:24:16.815819+00:00'
  claim_expires_at: '2026-08-03T16:54:16.815819+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
oompah.agent_run_id: 5d2db909-70ca-4b78-bdd3-efcc8a876844
---
## Summary

Triggered by: EXOCOMP-145

Production regression observed on EXOCOMP-145. The task was integrated successfully at b0d047ea97d00deb5c9b83054ddfb6de1491f0a9, but its last independent Done audit failed only because the required pinned Makefile gate output was missing. The operator subsequently ran make test, make fmt-check, and make lint successfully on that exact pushed head and recorded the raw tails. No code change was needed. Every integration completion sweep now logs 'Integrated task EXOCOMP-145 could not enter terminal audit: already completed' and leaves the task Ready to Integrate forever. OOMPAH-577 permits a fresh audit only when the evidence fingerprint changes; OOMPAH-720 intentionally excludes comments and audit bookkeeping from that fingerprint. The result is no automatic or ordinary audited recovery path for valid evidence-only remediation.

Implementation scope:
- Reproduce a failed terminal audit whose implementation head and canonical code fingerprint remain unchanged while required operator/quality-gate evidence is subsequently supplied.
- Add an authenticated, explicit, race-safe way to supersede the failed record and enqueue one fresh audit for the same target/fingerprint when remediation is evidence-only.
- Integrate that recovery with the integration completion sweep so an integrated task cannot log 'already completed' indefinitely without an actionable state, alert, or supported rearm operation.
- Preserve fail-closed behavior for unchanged incomplete work: arbitrary comments and non-owner actors must not rearm audits, and a successful completed audit must remain idempotently final.
- Preserve audit history, actor/reason attribution, independent-candidate requirements, ownership fencing, and exact task/integrated SHA evidence.
- Consider extending the existing owner --audit-retry path beyond infrastructure-only exhaustion with an explicit evidence-addendum contract rather than inventing a parallel terminal mutation.

Required tests:
- EXOCOMP-145 regression: failed missing-evidence audit, same integrated SHA, authenticated evidence remediation, fresh Pending/In Validation audit, then PASS to Done.
- Non-owner and arbitrary-comment attempts cannot rearm.
- Repeated identical owner rearm requests coalesce and cannot create duplicate auditors.
- Genuine code/evidence fingerprint changes continue through OOMPAH-577 behavior.
- Previously successful same-fingerprint audits remain non-rearmable.
- Sweep/restart races converge without repeated warning spam or a Ready-to-Integrate deadlock.
- Run focused terminal coordinator/API/integration tests and make test.

Acceptance criteria:
- An integrated same-head task can recover from an evidence-only audit failure through one documented authenticated action and return to independent audit.
- The integration sweep never leaves such a task indefinitely Ready with only an 'already completed' log line.
- No implementation or terminal authority boundary is weakened.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-03 16:24
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-08-03 16:24
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
