---
id: OOMPAH-646
type: task
status: Open
priority: null
title: Serialize review capacity across reconciliation sweeps and webhook lag
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:55:23.505409Z'
updated_at: '2026-07-31T06:56:32.233509Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.duplicate_screening:
  schema_version: 1
  task_fingerprint: 8cea44fcdd02f4e924fa57935fdd74f9d999884b52f2399da3ce04e65229127f
  detector_version: duplicate-detector-v1
  verdict: inconclusive
  checked_at: null
  matched_identifiers: []
  evidence: ''
  claim_id: 88ed357b-e7ea-4a2d-a67b-5c0f1d8642e2
  claim_owner: d12922aa-baf6-4258-aa45-02da3deea710
  claimed_at: '2026-07-31T06:56:14.634093+00:00'
  claim_expires_at: '2026-07-31T07:26:14.634093+00:00'
  retry_count: 0
  retry_after: null
oompah.agent_run_id: 82a8e8db-83ea-4947-9d39-662adb370655
---
## Summary

Live regression on 2026-07-31: project proj-14849f1b has max_in_flight_prs=1. PR #608 for OOMPAH-640 remained OPEN, CLEAN, and fully green while a later standalone Ready reconciliation created PR #609 for OOMPAH-642 at 06:53:54. OOMPAH-598 fixed same-sweep local reservation, but review capacity was again exceeded across successive sweeps/cache or webhook timing. Implementation scope: make review-slot acquisition authoritative and durable across reconciliation sweeps, concurrent webhook/review refreshes, branch-gate completions, and process restart. Acquire a per-project compare-and-swap lease/reservation before review creation, count existing open forge reviews plus durable unexpired reservations, commit the reservation to the created review identity, and release it on merge/close/create failure. Stale cached review data must never permit a second review when the forge still reports an open one. Preserve retryability for deferred Ready tasks and avoid false stranded-delivery alerts. Relevant files include standalone Ready reconciliation, _project_review_capacity/_count_open_reviews, review cache/webhook updates, review creation, and persisted delivery/review state. Required tests: deterministic later-sweep reproduction with stale cache after first PR creation; concurrent reconciliation and webhook timing; existing green-but-not-yet-merged PR; create failure; restart with reservation; merge/close releases slot; two projects remain isolated. Acceptance: with max_in_flight_prs=1 exactly one of two Ready branches owns an open PR until that PR is actually closed or merged, focused delivery/review tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-31 06:56
---
Duplicate screening dispatched (profile: default, task remains Open)
---
author: oompah
created: 2026-07-31 06:56
---
Focus: Duplicate Investigator
---
<!-- COMMENTS:END -->
