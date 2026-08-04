---
id: OOMPAH-767
type: epic
status: Open
priority: 1
title: Prove safety and eventual progress with model-based fault testing
parent: OOMPAH-763
children:
- OOMPAH-789
- OOMPAH-790
- OOMPAH-792
- OOMPAH-797
blocked_by: []
start_blocked_by: &id001
- OOMPAH-764
labels: []
assignee: null
created_at: '2026-08-04T13:55:58.011307Z'
updated_at: '2026-08-04T17:57:16.364231Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Build the verification system for the workflow engine. Implement an in-memory reference model and stateful/property-based generator for task graphs, nested epics, cross-epic dependencies, authority generations, audits, reviews, and jobs. Randomize valid events and inject duplicate/dropped events, stale snapshots, server death after every persistence step, Git fetch failures, deleted branches, changed PR targets, expired leases, authority changes, transport failures, and concurrent API/scheduler transitions. Assert safety after every operation and eventual progress once recoverable failures stop. Convert OOMPAH-562/731/732/739/748/749/751 into permanent full-stack scenarios. Add real temporary Git/native Markdown multi-project fixtures, a 100-task mixed workload soak, deterministic seeds, failure trace shrinking/replay, and CI runtime bounds. Acceptance: no invariant violation under the configured randomized campaign; all recoverable faults converge without manual tracker mutation; 100-task soak meets liveness SLOs; UI and executor decisions agree for every task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

