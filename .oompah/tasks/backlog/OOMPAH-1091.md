---
id: OOMPAH-1091
type: bug
status: Backlog
priority: 1
title: Stop stale accepted-validation recovery after repaired branch advances
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- workflow-liveness
assignee: null
created_at: '2026-08-11T15:35:51.682286Z'
updated_at: '2026-08-11T15:35:51.682286Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: stale-accepted-validation-recovery-after-branch-advance-v1
  request_fingerprint: 06d8f22fc277fa73860a8bc4eb5f0a9186117394a1000d66baab926583e755a8
---
## Summary

Triggered by: OOMPAH-1085

Live reproduction on OOMPAH-1085: the task is In Progress under a valid direct-owner claim at repaired exact head dcb52a5110f91cab5b6b732f5378ba13fb6a4d27, but retained oompah.integration accepted-submission metadata still names old head 7bd90702b13bfa876f49e5b4e5e27483997945b6. Every workflow reconciliation recreates the old validation_submission generation; repeated jobs reach transition_intent and supersede with transition.generation_mismatch, leaving universal liveness permanently degraded at required_recovery_count=4/materialized_recovery_count=3 even though no task is currently blocked. Repair workflow decision/recovery authority so when an In Progress repaired or direct-owner branch advances beyond a retained accepted submission, the impossible old-head validation obligation is parked/revoked or rebound only through an exact current-head submission; do not silently validate or publish the new head without submission, do not edit tracker metadata out of band, and preserve exact-head/CAS fail-closed behavior. Relevant areas include workflow decision/controller recovery materialization, validation submission authority/revocation, integration metadata reconciliation, and liveness projections. Add deterministic tests for branch advance before and across restart/reconcile, repeated ticks without generation-mismatch job churn, correct direct-owner behavior, exact current-head resubmission convergence, and recovery counts returning complete with no unexplained divergence. Run focused workflow/controller/liveness/submission tests, restart reconstruction tests, terminal mutation scan, and the canonical branch gate. Acceptance: no stale old-head validation job is regenerated after branch advance; no current-head validation is fabricated; exact resubmission converges once; required and materialized recovery counts agree; health is not degraded; and concurrent tracker/main changes remain fail closed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

