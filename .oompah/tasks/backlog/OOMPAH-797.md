---
id: OOMPAH-797
type: task
status: Backlog
priority: 1
title: Qualify the workflow engine with a multi-project 100-task soak
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-792
- OOMPAH-796
- OOMPAH-805
labels: []
assignee: null
created_at: '2026-08-04T13:59:28.518646Z'
updated_at: '2026-08-04T21:31:16.149778Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Build a deterministic production-like workload with at least 100 tasks across projects, independent tasks, shared/nested epics, cross-epic dependencies, reviews, audits, retries, branch pruning, and injected transient failures. Measure liveness SLOs, fairness, queue age, job retries, restart reconstruction, decision/UI parity, memory/SQLite growth, and alert actionability. Integrate a bounded version into CI and retain a longer operator soak target. Acceptance: all recoverable work reaches terminal state without manual intervention, only deliberately unrecoverable cases escalate, no task remains unexplained, and resource use stays within documented bounds.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

