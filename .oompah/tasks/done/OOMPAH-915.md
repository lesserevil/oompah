---
id: OOMPAH-915
type: task
status: Done
priority: null
title: Eliminate cross-thread project-lock deadlock in API status transitions
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T14:27:22.190077Z'
updated_at: '2026-08-09T21:42:57.944508Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-728273cf0f78
    project_id: proj-14849f1b
    task_id: OOMPAH-915
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 50390231d65df26641185d46b1e92eb71d6c9d1744cecd0ed52db95990fd4350
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:25:59.422878+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-915
    target_state: Done
    evidence_fingerprint: 50390231d65df26641185d46b1e92eb71d6c9d1744cecd0ed52db95990fd4350
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:26:12.294769+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Owner-reviewed terminal implementation is retained. The Done child is
      durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
      exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
    marked_at: '2026-08-09T21:42:56.484836+00:00'
    updated_at: '2026-08-09T21:42:56.484836+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Owner-reviewed terminal implementation is retained. The Done child is
        durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
        exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
      recorded_at: '2026-08-09T21:42:56.484836+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

The live OOMPAH-912 Backlog to Open PATCH reached durable transition APPLYING and then froze the entire server. api_update_issue holds project_store.project_write_lock on the ASGI thread, calls synchronous _apply_task_status_transition, and Orchestrator._transition_issue_status detects the running event loop and waits on a helper thread. ProvenanceGuardedTracker.update_issue on that helper tries to acquire the same thread-owned RLock, producing a deterministic deadlock; health checks, task reads, graceful restart, and stop all then time out. OOMPAH-910 fixed the analogous owner-revision path but not ordinary API status transitions.\n\nImplementation scope:\n- Remove the outer project lock from across durable status-transition execution; the provenance tracker/transition writer must acquire write authority on the execution thread that performs the mutation.\n- Prefer the async transition service at the async API boundary so the event loop is not blocked on a helper-thread future.\n- Split mixed status/metadata updates into bounded lock phases with current-authority revalidation and preserve atomic/fail-closed behavior.\n- Audit sibling API transition paths for the same outer-lock plus helper-thread topology.\n\nRequired tests:\n- Exercise async Backlog to Open with a real threading.RLock and provenance-guarded tracker under a bounded timeout; prove one committed transition, no lingering claim, and a responsive concurrent health/event-loop probe.\n- Cover combined status and metadata updates, owner promotion, transition rejection, and concurrent writers.\n- Retain OOMPAH-910 owner-revision regressions.\n\nAcceptance criteria:\n- API lifecycle updates cannot deadlock the server through cross-thread recursive project locking.\n- The event loop remains responsive during tracker I/O.\n- Focused server, orchestrator transition, and provenance locking tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 14:37
---
Direct owner implementation completed locally on the systemic composition branch. Async API status transitions no longer hold a request-thread project RLock across worker-thread tracker I/O; mixed metadata writes use a bounded writer-thread lock and revalidation. Focused runtime/status/server suites pass. Status remains Backlog until the expired-transition recovery fix is deployed.
---
author: oompah
created: 2026-08-08 16:26
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope is contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
