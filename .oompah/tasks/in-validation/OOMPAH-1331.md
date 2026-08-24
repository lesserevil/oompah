---
id: OOMPAH-1331
type: task
status: In Validation
priority: null
title: Restart reconstruction never finalizes (1 unexplained divergence) leaving stale
  action_required=19 and permanent restart_overdue
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-24T16:28:31.897753Z'
updated_at: '2026-08-24T17:00:04.351394Z'
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
  creation_marker: eaae4288-c737-4655-a501-a014d7a120f1
  request_fingerprint: 0424978c962567958aad57a379d453e5110704b8c4b1b80170bf0f08fca47f38
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-34bc00c97981
    project_id: proj-14849f1b
    task_id: OOMPAH-1331
    digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
  - version: 1
    audit_id: audit-ad3efba187b4
    project_id: proj-14849f1b
    task_id: OOMPAH-1331
    digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-34bc00c97981
    project_id: proj-14849f1b
    task_id: OOMPAH-1331
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T16:59:53.820238+00:00'
    eligible_at: '2026-08-24T16:59:53.820238+00:00'
    selected_ref: origin/OOMPAH-1331
    selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
  - version: 1
    audit_id: audit-ad3efba187b4
    project_id: proj-14849f1b
    task_id: OOMPAH-1331
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 2f42f5bc26ff73d05a270cfeb550a9d34cd30dc3c7f4182f4f49ddc36d258bd9
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-24T16:59:53.820238+00:00'
    prerequisite_audit_id: audit-34bc00c97981
    selected_ref: origin/OOMPAH-1331
    selected_sha: c98f49444f27de8d3faba8e80c791632e52220e5
  attempt_history: []
oompah.lifecycle_revision: 1
---
## Summary

### Problem
workflow_liveness restart reconstruction never marks complete, so the dashboard permanently shows 'N workflow task(s) require a named human action' (source workflow_liveness:action_required) with a frozen count (observed action_required=19). Worker admission stays fenced (worker.skipped: 'workflow publication requires reconciliation before durable admission').

### Live evidence (build 1e08d58a3, main)
- workflow_liveness.restart: reconstruction_pending=true, started_at=2026-08-24T15:41:44Z (does NOT reset across a graceful make restart), lateness_seconds keeps growing (>2000s), convergence_count=132.
- workflow_liveness.reconciliation: complete=false, required_recovery_count=83, materialized_recovery_count=83 (all required recoveries materialized).
- missing_decision_count=0, current_divergence_count=1, unexplained_divergence_count=1, evaluated_count=0, total_nonterminal_count=320.
- workflow_runtime.last_reconcile alternates between requires_reconcile=null and (earlier) requires_reconcile=true reason=publication_authority_changed; worker=skipped.
- The frozen action_required=19 persists across a full service restart and with zero running agents, i.e. it is a stale pre-scan projection that never refreshes because scan_complete stays false.

### Impact
- Non-terminal work cannot be admitted (integration/implementation stay idle) while reconstruction is pending.
- Operators see a persistent, non-actionable 'named human action' alert that does not correspond to 19 real tasks (the per-task records are unpopulated: id/action/reason all null).

### Suspected root cause
Restart reconstruction finalization requires zero unexplained divergences, but 1 unexplained divergence remains even though required_recovery_count == materialized_recovery_count (83) and missing_decision_count == 0. Reconstruction therefore never sets reconciliation.complete=true / scan_complete=true, and the restart record is persisted (not reset) so a restart does not clear it. This is distinct from OOMPAH-1329 (over-budget scoped/deadline supersession) and from the auditor transport crash (OOMPAH-1330).

### Investigation scope
- Find where restart reconstruction decides completeness (workflow_liveness / workflow_runtime restart_reconstruction path) and why a single unexplained divergence blocks finalization after all required recoveries are materialized.
- Identify the specific diverging record (current_divergence_count=1) and classify it; ensure an explained/reconciled divergence cannot remain 'unexplained' forever.
- Ensure restart reconstruction state resets or re-evaluates cleanly on service restart rather than persisting a stuck started_at/deadline.
- Ensure the dashboard action_required projection refreshes (or is suppressed) when scan_complete=false rather than surfacing a stale count.

### Tests
- Reconstruction with all required recoveries materialized and 1 residual explained-but-flagged divergence must still converge to complete=true.
- Restart reconstruction record resets/re-evaluates across runtime restart.
- action_required projection is not surfaced as a stale frozen count while scan_complete=false.

### Acceptance Criteria
- After recoveries are materialized and no genuine human action is pending, restart reconstruction converges (scan_complete=true, reconstruction_pending=false), worker admission reopens, and the 'require a named human action' alert clears.
- A single unexplained divergence cannot indefinitely block finalization.
- A graceful restart re-evaluates reconstruction rather than inheriting a permanently-late record.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-24 17:00
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
