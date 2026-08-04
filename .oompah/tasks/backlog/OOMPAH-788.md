---
id: OOMPAH-788
type: feature
status: Backlog
priority: 1
title: Cut integration delivery over to shared decisions and durable jobs
parent: OOMPAH-768
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T13:59:10.953215Z'
updated_at: '2026-08-04T13:59:10.953215Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Migrate integration submission, eligibility, dependency satisfaction, claim, quality gate, ancestry repair, retry, terminal staging, and queue UI to WorkflowFacts/WorkDecision/workflow jobs/TaskTransitionService. Evaluate all topological heads rather than only the first Ready row; unify executor eligibility, metrics, waiting_on, and repair selection; preserve exact-head leases, fairness, audit staging, and historical queue migration. Required tests: mixed repairable/unrepairable rows, cross-epic reachability, hundreds of history rows, restart, retries, capacity, branch deletion, UI parity, and OOMPAH-562/749 scenarios. Acceptance: one integration decision powers execution and UI; every Ready task is claimed, concretely blocked, retry-scheduled, or escalated within SLO.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

