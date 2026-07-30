---
id: OOMPAH-628
type: bug
status: Backlog
priority: 1
title: Rearm explicitly resubmitted integrated queue rows
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T22:37:04.318940Z'
updated_at: '2026-07-30T22:37:04.318940Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Implementation scope: distinguish an explicit operator resubmission of a task whose tracker lifecycle was deliberately returned to Ready to Integrate from background synchronization of an already-integrated queue row. Allow the explicit API/CLI submit path to rearm the identical task branch and head only when the canonical task integration record is newly Ready, while preserving idempotency for duplicate submissions in Ready or Integrating and for periodic synchronization. This repairs the observed OOMPAH-627 state where supported Done-to-Ready reflow wrote a new ready integration record but IntegrationQueueStore.enqueue returned the old integrated row forever. Relevant files: oompah/integration_queue.py, server submission wiring, orchestrator synchronization, and focused queue/submission tests. Tests must reproduce same-head integrated explicit reflow, prove background sync remains integrated/idempotent, prove ordinary duplicate active submissions do not reset leases or attempts, and run the focused tests plus the Makefile gate. Acceptance criteria: an explicitly reflowed same-head task cannot remain stranded in Ready to Integrate behind an integrated durable row; no automatic duplicate integration loop is introduced; all focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

