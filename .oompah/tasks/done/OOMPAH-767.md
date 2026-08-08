---
id: OOMPAH-767
type: epic
status: Done
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
updated_at: '2026-08-08T16:30:47.427460Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.start_blocked_by: *id001
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-9d9f4206e875
    project_id: proj-14849f1b
    task_id: OOMPAH-767
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b695527aee044b555192232c241e6b6ed8e5519ddd6897a9a2141ba396e86dec
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope and its completed dependency wave are contained in that validated
      head; owner override avoids fabricating a separate branch/integration generation.
    created_at: '2026-08-08T16:30:43.362458+00:00'
    applied: false
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Build the verification system for the workflow engine. Implement an in-memory reference model and stateful/property-based generator for task graphs, nested epics, cross-epic dependencies, authority generations, audits, reviews, and jobs. Randomize valid events and inject duplicate/dropped events, stale snapshots, server death after every persistence step, Git fetch failures, deleted branches, changed PR targets, expired leases, authority changes, transport failures, and concurrent API/scheduler transitions. Assert safety after every operation and eventual progress once recoverable failures stop. Convert OOMPAH-562/731/732/739/748/749/751 into permanent full-stack scenarios. Add real temporary Git/native Markdown multi-project fixtures, a 100-task mixed workload soak, deterministic seeds, failure trace shrinking/replay, and CI runtime bounds. Acceptance: no invariant violation under the configured randomized campaign; all recoverable faults converge without manual tracker mutation; 100-task soak meets liveness SLOs; UI and executor decisions agree for every task.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

