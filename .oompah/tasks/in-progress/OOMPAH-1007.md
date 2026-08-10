---
id: OOMPAH-1007
type: task
status: In Progress
priority: null
title: Fence completed terminal-audit recurrence to current workflow completion authority
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T23:19:04.544332Z'
updated_at: '2026-08-10T23:19:55.698021Z'
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
  creation_marker: 9dc1401e-893a-4d78-b780-e075b80e6ca4
  request_fingerprint: c095f7baf028623fb2e3b627aeb5c1d76005844bc667a2b87478b4a5a96db285
---
## Summary

Live reproduction on deployed main 74e68a020: OOMPAH-940 naturally completed epic auto-close and staged fresh Done/Merged audits after all systemic descendants landed and the protected full gate passed. The new audit records audit-9ac757c7ad64/audit-47936c819189 nevertheless reused issue evidence fingerprint 0a8f66cc from the August 9 root-branch audit at 2dd74be2. TerminalTransitionCoordinator.reconcile_completed_recurrence_sync therefore replayed the historical ci_failure as workflow-recurrence:audit-9ac757c7ad64 without a new attempt and moved OOMPAH-940 from In Validation to Needs CI Fix. The canonical workflow terminal decision/evidence had advanced through later protected descendant deliveries, but recurrence authority observed only the unchanged root issue fingerprint.\n\nImplementation scope: bind completed terminal-audit recurrence to the complete current terminal workflow authority, not merely a root issue fingerprint that can remain unchanged while canonical child/descendant landing and quality evidence advances. A prior completed PASS or FAIL may be reused only when both the task fingerprint and the authoritative workflow terminal eligibility/quality revision are identical. When workflow completion authority advances, supersede/retire the obsolete recurrence source and queue one fresh exact audit (or reuse an exact current authoritative passing gate through the existing policy) without applying the old result. Preserve immutable audit history, identical-evidence idempotency, Done→Merged ordering, project/task/fingerprint CAS, stale-worker rejection, fail-closed behavior for missing/ambiguous authority, pause/restart semantics, and owner-override safety. Relevant code: oompah/terminal_transition_coordinator.py completed recurrence, terminal transition request fingerprint/binding, durable workflow transition/effect plumbing in oompah/workflow_runtime.py and epic auto-close paths, and terminal audit persistence/dispatch.\n\nRequired tests: reproduce OOMPAH-940 with an old completed ci_failure at root head E0, then a fresh workflow auto-close whose root issue fingerprint is still E0 but whose canonical completion authority has advanced; prove the old failure is not replayed, exactly one fresh chain is admitted, and the task does not return to Needs CI Fix. Controls must prove truly identical workflow authority still replays PASS and FAIL idempotently; changed/absent/ambiguous authority fails closed; Done/Merged chain ordering, restart between stage/reconcile, concurrent recurrence/result CAS, and project isolation remain correct. Run focused coordinator/workflow/epic tests, terminal mutation scan, and make test. Acceptance: after deployment, OOMPAH-940 can re-enter the natural terminal path without reusing audit-fddacbaa91fb solely because 0a8f66cc is unchanged; current authoritative evidence decides the audit, current exhausted/divergence stay zero, and workflow-rollout-check passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

