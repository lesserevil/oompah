---
id: OOMPAH-794
type: task
status: Backlog
priority: 1
title: Delete superseded reconcilers, watchdog heuristics, and duplicate workflow
  predicates
parent: OOMPAH-771
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-797
- OOMPAH-795
labels: []
assignee: null
created_at: '2026-08-04T13:59:23.320051Z'
updated_at: '2026-08-04T14:07:35.263879Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

After domain enforcement and soak gates, remove legacy eligibility summaries, direct status writers, read-time repair side effects, status-specific watchdog remediation, old integration/audit/review/epic reconcilers, obsolete process-local authority/cooldown maps, and fire-and-forget lifecycle futures. Retain only non-lifecycle housekeeping maintenance. Add architectural tests preventing reintroduction. Required tests: full make test, API compatibility, upgrade/restart with legacy persisted state, and WorkDecision parity. Acceptance: no dual workflow path remains; legacy deletion is measured and production workflow LOC/branch complexity decline materially.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

