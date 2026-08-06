---
id: OOMPAH-792
type: task
status: Open
priority: 1
title: Run all historical systemic incidents as full-stack workflow scenarios
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-789
- OOMPAH-788
- OOMPAH-781
- OOMPAH-782
- OOMPAH-793
- OOMPAH-791
- OOMPAH-804
labels: []
assignee: null
created_at: '2026-08-04T13:59:19.563806Z'
updated_at: '2026-08-06T16:09:26.788374Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 00c6dc9f9b1664fbf306e3f01847f4abb61a50803db350a17aa072db95634e10
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: b129deef-9ba2-4795-ba6d-2dd13106fb61
  claim_owner: d499f6a6-5717-4e4a-8ad7-bc38cc47251d
  claimed_at: '2026-08-06T16:09:25.323355+00:00'
  claim_expires_at: '2026-08-06T16:39:25.323355+00:00'
  retry_count: 0
  retry_after: null
  owner_resolved_at: null
  owner_login: null
  owner_resolution_reason: ''
---
## Summary

Use the shared incident corpus to build full-stack scenarios spanning fact collectors, evaluator, job ledger/worker, transition service, native tracker, Git, and UI projection for OOMPAH-562/731/732/739/748/749/751. Avoid mocking the exact boundary whose composition caused the incident. Verify both safety and bounded natural recovery, including server restart and event duplication. Acceptance: every historical workaround scenario progresses without manual status/queue/branch mutation and produces the same reason in executor and UI.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-06 16:08
---
All seven hard-start prerequisites are terminal and the live dependency audit found no remaining start blocker. Promoted to Open so the managed server can implement the historical full-stack scenario suite in parallel with operator-owned repair integration.
---
<!-- COMMENTS:END -->
