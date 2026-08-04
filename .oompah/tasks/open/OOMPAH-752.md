---
id: OOMPAH-752
type: bug
status: Open
priority: 1
title: Select standalone Ready delivery fairly before claiming task authority
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T01:54:29.023994Z'
updated_at: '2026-08-04T01:54:38.252496Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-749

Live regression on revision c54a60a6, which already contains OOMPAH-732. After PR 698 freed Oompah review capacity, standalone Ready tasks OOMPAH-735, OOMPAH-746, OOMPAH-748, OOMPAH-749, and OOMPAH-750 were all eligible. Each sweep logged Cancelled superseded standalone delivery before review lookup for the older tasks, while only newest OOMPAH-750 reached the capacity check and started the full quality gate. This makes delivery effectively LIFO and permits indefinite starvation when Ready work continues arriving; OOMPAH-749 is the live queue-recovery fix whose delay leaves 37 shared integration rows at attempts=0. Implementation scope: build the eligible standalone set first, resolve dependencies and review or gate capacity once, and select a bounded candidate with stable priority plus FIFO submitted-at ordering before claiming delivery authority or doing remote work. Do not issue and revoke authorities for unselected tasks; retain a truthful non-actionable capacity-wait state. If the selected candidate is invalid or undeliverable, record its actionable reason and consider the next eligible candidate in the same bounded sweep. Preserve exact-head fencing, existing-review adoption, per-project capacity, same-head retry, dependency ordering, and OOMPAH-732 separation from shared queue processing. Relevant code: _reconcile_standalone_ready_to_integrate_tasks, standalone authority claim and refresh, Ready tracker ordering, BranchQualityGate ownership, and review-capacity reservations. Required tests: five simultaneous Ready tasks where the oldest eligible task gates first; continuous new arrivals cannot overtake an older row; high priority precedes lower priority with FIFO ties; dependency-blocked and invalid-head rows do not block the next eligible task; list/detail representations remain authority-equivalent; restart, existing PR, gate failure, and capacity wait. Acceptance criteria: every eligible standalone Ready task receives a bounded delivery turn without LIFO starvation, unselected tasks are not reported as superseded, and OOMPAH-749 can reach review without manual delivery.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

