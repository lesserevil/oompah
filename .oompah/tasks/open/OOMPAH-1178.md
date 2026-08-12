---
id: OOMPAH-1178
type: feature
status: Open
priority: 2
title: Support transactional batch task updates for whole-column moves
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- needs:frontend
- needs:backend
- human-only
assignee: null
created_at: '2026-08-12T15:56:01.307393Z'
updated_at: '2026-08-12T17:33:30.532856Z'
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
  creation_marker: feature-batch-task-updates-column-drag-20260812
  request_fingerprint: 5ec1af9a834162f7aa2e2169a817eb3f0af7a9ac6c84ed06d3cafcbe59b9190f
---
## Summary

Add a first-class batch task mutation API and dashboard interaction for moving many tasks between workflow states in one operation, especially when an operator drags an entire Kanban column to another state. The browser must send one API request containing the project, ordered task identifiers, target status, and per-task expected revision/generation evidence instead of issuing one request per card. The backend must validate authorization, workflow transition legality, dependencies, terminal-state policy, owner claims, and exact task generations for the complete batch before applying mutations.

API design scope: introduce a versioned project-scoped batch endpoint (for example POST /api/v1/projects/{project_id}/tasks/batch-update) with a bounded request size, idempotency key, actor derived from authentication, operation metadata, and an ordered list of task mutations. Define clear all-or-nothing semantics for task backends that support atomic transactions. For backends that cannot provide a single native transaction, expose a storage-adapter batch primitive that minimizes fetch/commit/push operations, performs one preflight over the full set, uses deterministic ordering and compensation/reconciliation where needed, and returns an explicit atomicity/capability result rather than silently degrading into unobservable partial success. The response must include per-task results, committed revisions, batch identity, event sequence/cursor information, and actionable rejection details. Retrying the same idempotency key must never apply a transition twice.

Storage scope: extend the tracker/storage abstraction with bulk read, validate, mutate, and commit support. Native Markdown/state-branch storage should apply the complete set in one locked worktree transaction and preferably one state-branch commit/push. Database-backed storage should use one database transaction. Remote trackers should use their native batch facilities when available or a bounded minimal-call strategy with durable recovery for partial remote effects. Avoid N independent synchronization cycles and N full state refreshes; coalesce workflow reconciliation, WebSocket publication, audit scheduling, parent/epic rollups, and board refresh into the smallest safe number of operations after commit.

Dashboard scope: provide an accessible whole-column move affordance, including drag/drop where practical plus keyboard/menu fallback. Show the destination and task count before committing, require confirmation for large or policy-sensitive moves, retain the column locally until the server result is known, render per-task rejection details without losing selection, and reconcile from the authoritative batch response/full snapshot. Ordinary single-card drag behavior must remain unchanged. A batch should produce one cohesive UI progress state rather than dozens of independent toasts and rerenders.

Safety and concurrency: reject the complete batch before mutation when any expected revision is stale under atomic mode; return current evidence so the client can refresh and retry. Define behavior for terminal transitions, mixed current states, invalid transitions, dependencies, tasks with active agents/audits/integration leases, paused projects, duplicate identifiers, cross-project identifiers, and concurrent batches. Authorization must be evaluated from the authenticated principal, including owner-only Backlog -> Open promotion. Emit durable provenance for the batch and each affected task without duplicating WebSocket events or scheduler work.

Required tests: API schema and size limits; authenticated actor behavior; successful whole-column transition; idempotent retry; one stale member causing zero changes; mixed legal/illegal transitions; owner-only promotion; active-agent and lease conflicts; terminal/audit policy; concurrent overlapping batches; state-branch single-commit behavior; database single-transaction rollback; remote-adapter partial-effect recovery; coalesced workflow/event/rollup refresh; WebSocket sequence continuity; dashboard whole-column drag, confirmation, keyboard fallback, optimistic display, rejection recovery, and no N-request regression. Include performance instrumentation comparing batch storage transactions/API calls with the prior per-card loop.

Acceptance criteria: moving a column of tasks is performed with one client API request; the backend validates the set as a unit and applies it with the minimum safe number of storage transactions; native Markdown and database storage are all-or-nothing; non-atomic remote capabilities are explicit and recoverable; retries are idempotent; no task is silently lost or partially moved; scheduler, audit, rollup, alerts, and WebSocket projections converge once to the committed batch; accessible UI behavior and existing single-task updates remain correct; focused tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

