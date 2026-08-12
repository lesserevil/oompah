---
id: OOMPAH-1178
type: feature
status: Merged
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
updated_at: '2026-08-12T20:02:26.874548Z'
work_branch: OOMPAH-1178
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/837
review_number: '837'
review_head: aaa3ec17a0b98e280bffa1e71d3dd904f5060d41
merged_at: null
oompah.create_once:
  version: 1
  project_id: proj-14849f1b
  operation_kind: api_task_create
  creation_marker: feature-batch-task-updates-column-drag-20260812
  request_fingerprint: 5ec1af9a834162f7aa2e2169a817eb3f0af7a9ac6c84ed06d3cafcbe59b9190f
oompah.review_url: https://github.com/lesserevil/oompah/pull/837
oompah.review_number: '837'
oompah.work_branch: OOMPAH-1178
oompah.target_branch: main
oompah.review_head: aaa3ec17a0b98e280bffa1e71d3dd904f5060d41
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-041365d47abb
    project_id: proj-14849f1b
    task_id: OOMPAH-1178
    digest: 8c6fcb07f9ab40113d4cc90d8a0c5119374a976b47c0c7215c05f6490b549791
  - version: 1
    audit_id: audit-ff6ce97a0895
    project_id: proj-14849f1b
    task_id: OOMPAH-1178
    digest: 8c6fcb07f9ab40113d4cc90d8a0c5119374a976b47c0c7215c05f6490b549791
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6e780408ffd9
    project_id: proj-14849f1b
    task_id: OOMPAH-1178
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8c6fcb07f9ab40113d4cc90d8a0c5119374a976b47c0c7215c05f6490b549791
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Direct-owner completion verified in merged PR #837 at 00db66b58: transactional
      batch task updates and whole-column UI moves are implemented; focused suites
      passed 1,893 and 911 tests and full Python 3.11/3.12/3.13 CI passed.'
    created_at: '2026-08-12T20:02:22.339971+00:00'
    selected_ref: origin/OOMPAH-1178
    selected_sha: f1902e64d2cdef014e84a8cb1c58896ca1e40f35
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-041365d47abb
    project_id: proj-14849f1b
    task_id: OOMPAH-1178
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8c6fcb07f9ab40113d4cc90d8a0c5119374a976b47c0c7215c05f6490b549791
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-12T19:57:06.162756+00:00'
    eligible_at: '2026-08-12T19:57:06.162756+00:00'
    selected_ref: origin/OOMPAH-1178
    selected_sha: f1902e64d2cdef014e84a8cb1c58896ca1e40f35
  - version: 1
    audit_id: audit-ff6ce97a0895
    project_id: proj-14849f1b
    task_id: OOMPAH-1178
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 8c6fcb07f9ab40113d4cc90d8a0c5119374a976b47c0c7215c05f6490b549791
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Review
    created_at: '2026-08-12T19:57:06.162756+00:00'
    prerequisite_audit_id: audit-041365d47abb
    selected_ref: origin/OOMPAH-1178
    selected_sha: f1902e64d2cdef014e84a8cb1c58896ca1e40f35
  attempt_history: []
oompah.lifecycle_revision: 1
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 19:07
---
Direct-owner implementation is feature-complete on branch OOMPAH-1178. Added one-call project-scoped atomic batch status API, exact per-task CAS with monotonic lifecycle revisions, persistent idempotency receipts, crash-safe publishing recovery, single state-branch commit/push, explicit unsupported remote capabilities, owner/worker/audit/integration/transition fences, paused-project semantics, coalesced events/rollups, and accessible dashboard whole-column drag/keyboard flow. Focused integration evidence: 639 passed; terminal mutation scan 21/21 passed. The full make test gate is currently running on the exact working tree while all projects remain paused.
---
author: oompah
created: 2026-08-12 19:22
---
Committed and pushed as bbfb66b578e783c7ee319c93fd96c5bd11934394, then combined with OOMPAH-1177 on PR #837 at aaa3ec17a0b98e280bffa1e71d3dd904f5060d41. Exact-head expanded integration coverage passes 1,893 tests and the combined focused suite passes 911; terminal mutation scan passes 21/21. Full Makefile gate and GitHub matrix are running.
---
author: oompah
created: 2026-08-12 19:24
---
Branch quality gate passed for `aaa3ec17a0b98e280bffa1e71d3dd904f5060d41` using `make test` in 178.3s. Review creation may proceed.
---
author: oompah
created: 2026-08-12 19:57
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
