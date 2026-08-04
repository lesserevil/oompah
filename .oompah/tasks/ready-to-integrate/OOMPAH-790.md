---
id: OOMPAH-790
type: feature
status: Ready to Integrate
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
updated_at: '2026-08-04T17:56:35.800301Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  task_branch: OOMPAH-790
  head_sha: fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1
  submitted_at: '2026-08-04T17:56:29.186599+00:00'
  updated_at: '2026-08-04T17:56:29.186599+00:00'
---
## Summary

Implement an in-memory reference machine from the workflow contract plus generators for tasks, statuses, dependency DAGs/cycles, nested epics, landing facts, audits, reviews, ownership generations, retries, and jobs. Generate valid and adversarial event sequences with deterministic seeds and shrinkable/replayable failure traces. Assert transition safety, unique ownership, evidence fencing, total disposition, and eventual progress when faults cease. Add dependency and runtime bounds suitable for CI. Acceptance: the harness explores compositions beyond example tests, emits minimal reproducible traces, and fails on seeded versions of known systemic bugs.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 17:56
---
Implemented deterministic bounded state-machine generation, stable JSON replay, 1-minimal trace shrinking, dependency/cycle and nested-epic compositions, ownership/job generation fencing, terminal evidence checks, eventual-progress reconciliation, and seeded faulty policies proving detection of stale callbacks, duplicate owners, lost retry wakeups, and unproven terminal transitions. Verification: 79 reference-harness tests and 277 composed workflow tests pass; Ruff, terminal mutation scan, and secret scan pass. Exact pushed head: fee2b7a57f1f85b44b82cc23b4e6734d27d5e4d1.
---
author: oompah
created: 2026-08-04 17:56
---
Added and verified deterministic generative workflow reference harness at fee2b7a57.
---
<!-- COMMENTS:END -->
