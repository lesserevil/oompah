---
id: OOMPAH-1243
type: task
status: Backlog
priority: null
title: Ignore forge events delivered after epic event-router shutdown
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T14:32:43.240296Z'
updated_at: '2026-08-13T14:32:43.240296Z'
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
---
## Summary

Scope: make EpicWorkflowEventRouter shutdown idempotently reject or coalesce late forge events instead of submitting to an already-shutdown ThreadPoolExecutor. Live reproduction during the 2026-08-13 graceful auto-update: forge_webhook_received reached on_forge_event after Orchestrator stopped and raised RuntimeError: cannot schedule new futures after shutdown from _submit_ordered. Add an explicit closed/admission fence shared by close and every event entry point, preserve restart reconciliation as the recovery authority for rejected late events, and avoid emitting noisy handler tracebacks during normal drain. Relevant code: oompah/epic_workflow_adapter.py EpicWorkflowEventRouter._submit_ordered/on_forge_event/close and event-bus shutdown ordering. Tests must deterministically race close with a forge event and prove no future is submitted, no exception escapes EventBus.emit, and a pre-close accepted event is still drained exactly once. Acceptance: graceful restart logs contain no post-shutdown executor submission exception and no accepted event is silently lost without restart reconciliation authority.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

