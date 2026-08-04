---
id: OOMPAH-790
type: feature
status: In Progress
priority: 1
title: Build a stateful reference model and generative workflow harness
parent: OOMPAH-767
children: []
blocked_by: []
start_blocked_by: &id001
- OOMPAH-772
labels: []
assignee: null
created_at: '2026-08-04T13:59:16.097978Z'
updated_at: '2026-08-04T17:42:59.552731Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
---
## Summary

Implement an in-memory reference machine from the workflow contract plus generators for tasks, statuses, dependency DAGs/cycles, nested epics, landing facts, audits, reviews, ownership generations, retries, and jobs. Generate valid and adversarial event sequences with deterministic seeds and shrinkable/replayable failure traces. Assert transition safety, unique ownership, evidence fencing, total disposition, and eventual progress when faults cease. Add dependency and runtime bounds suitable for CI. Acceptance: the harness explores compositions beyond example tests, emits minimal reproducible traces, and fails on seeded versions of known systemic bugs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

