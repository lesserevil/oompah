---
id: OOMPAH-646
type: task
status: Backlog
priority: null
title: Serialize review capacity across reconciliation sweeps and webhook lag
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-31T06:55:23.505409Z'
updated_at: '2026-07-31T06:55:23.505409Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live regression on 2026-07-31: project proj-14849f1b has max_in_flight_prs=1. PR #608 for OOMPAH-640 remained OPEN, CLEAN, and fully green while a later standalone Ready reconciliation created PR #609 for OOMPAH-642 at 06:53:54. OOMPAH-598 fixed same-sweep local reservation, but review capacity was again exceeded across successive sweeps/cache or webhook timing. Implementation scope: make review-slot acquisition authoritative and durable across reconciliation sweeps, concurrent webhook/review refreshes, branch-gate completions, and process restart. Acquire a per-project compare-and-swap lease/reservation before review creation, count existing open forge reviews plus durable unexpired reservations, commit the reservation to the created review identity, and release it on merge/close/create failure. Stale cached review data must never permit a second review when the forge still reports an open one. Preserve retryability for deferred Ready tasks and avoid false stranded-delivery alerts. Relevant files include standalone Ready reconciliation, _project_review_capacity/_count_open_reviews, review cache/webhook updates, review creation, and persisted delivery/review state. Required tests: deterministic later-sweep reproduction with stale cache after first PR creation; concurrent reconciliation and webhook timing; existing green-but-not-yet-merged PR; create failure; restart with reservation; merge/close releases slot; two projects remain isolated. Acceptance: with max_in_flight_prs=1 exactly one of two Ready branches owns an open PR until that PR is actually closed or merged, focused delivery/review tests and terminal mutation scan pass, and make test passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

