---
id: OOMPAH-1243
type: task
status: Merged
priority: null
title: Ignore forge events delivered after epic event-router shutdown
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T14:32:43.240296Z'
updated_at: '2026-08-14T07:44:23.378019Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.create_once:
  version: 1
  project_id: oompah
  operation_kind: api_task_create
  creation_marker: 29621f3b-9c54-46af-b7b6-06d19d37bdc2
  request_fingerprint: c895038d585d523bed9b8f71df06ee02ebfa99a7fb4c824628559e0de21425d7
oompah.lifecycle_revision: 2
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-686d5ff9c434
    project_id: proj-14849f1b
    task_id: OOMPAH-1243
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fea9c013447f77bd2dc0710db245eae759a0f23836cef0474ce6bf0db1dc36cf
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #868 merged as 83196da17 and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:44:14.772002+00:00'
    selected_ref: origin/main
    selected_sha: 948ef6f207eabe4c26910d8fc276d6d36b659e76
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1243
    target_state: Merged
    evidence_fingerprint: fea9c013447f77bd2dc0710db245eae759a0f23836cef0474ce6bf0db1dc36cf
    workflow_revision: null
    selected_ref: origin/main
    selected_sha: 948ef6f207eabe4c26910d8fc276d6d36b659e76
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-14T07:44:22.237504+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Scope: make EpicWorkflowEventRouter shutdown idempotently reject or coalesce late forge events instead of submitting to an already-shutdown ThreadPoolExecutor. Live reproduction during the 2026-08-13 graceful auto-update: forge_webhook_received reached on_forge_event after Orchestrator stopped and raised RuntimeError: cannot schedule new futures after shutdown from _submit_ordered. Add an explicit closed/admission fence shared by close and every event entry point, preserve restart reconciliation as the recovery authority for rejected late events, and avoid emitting noisy handler tracebacks during normal drain. Relevant code: oompah/epic_workflow_adapter.py EpicWorkflowEventRouter._submit_ordered/on_forge_event/close and event-bus shutdown ordering. Tests must deterministically race close with a forge event and prove no future is submitted, no exception escapes EventBus.emit, and a pre-close accepted event is still drained exactly once. Acceptance: graceful restart logs contain no post-shutdown executor submission exception and no accepted event is silently lost without restart reconciliation authority.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 14:40
---
Implemented an explicit EpicWorkflowEventRouter close/admission fence. Already accepted work drains exactly once; late events and shared-pool shutdown races resolve as restart-reconciled no-ops instead of escaping RuntimeError. Added deterministic close/late-delivery tests. Focused suite: 103 passed; terminal mutation and secret scans passed.
---
author: oompah
created: 2026-08-14 07:44
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #868 merged as 83196da17 and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
