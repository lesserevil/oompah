---
id: OOMPAH-794
type: task
status: In Progress
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
updated_at: '2026-08-08T12:03:02.994240Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 09:20
---
Independent implementation complete for composition: commit 31710c44741fca893d0b1663c83378defaa5a9f4 on direct/OOMPAH-794-on-systemic, based on e48d953e45e9e39933d86b46bf0b11faedd6a008. Runtime installation is now a one-way lifecycle authority boundary; legacy startup/tick/refresh/retry fallbacks cannot run in off/shadow. Focused high-risk suites passed (314 authority-fallback, 163 restart/event, final 16 regression); terminal mutation scan passed. Full broker: 18,557 passed with 16 unrelated composed-head failures. No push or status change performed.
---
<!-- COMMENTS:END -->
