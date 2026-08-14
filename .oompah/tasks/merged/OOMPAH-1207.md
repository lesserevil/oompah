---
id: OOMPAH-1207
type: bug
status: Merged
priority: 1
title: Restart reconstruction recognizes protected imperative implementation jobs
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T02:28:41.440593Z'
updated_at: '2026-08-14T07:30:21.045034Z'
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
  creation_marker: restart-protected-imperative-deadlock-v1
  request_fingerprint: 797202381757f69a5b53e55ce41290011c271fb8242330dce8c5fd860a7a71c8
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-371f4e17043f
    project_id: proj-14849f1b
    task_id: OOMPAH-1207
    digest: 6a2d89d1b8e58b16d1963ea3fabedd5d634aa38094a37fa6afd43d5930ab07c1
  - version: 1
    audit_id: audit-0fdf1367d086
    project_id: proj-14849f1b
    task_id: OOMPAH-1207
    digest: 6a2d89d1b8e58b16d1963ea3fabedd5d634aa38094a37fa6afd43d5930ab07c1
  oompah.terminal_override_records:
  - version: 1
    override_id: override-6a186a9da2ad
    project_id: proj-14849f1b
    task_id: OOMPAH-1207
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a2d89d1b8e58b16d1963ea3fabedd5d634aa38094a37fa6afd43d5930ab07c1
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Owner convergence: PR #846 merged as 683b5f34a and that landed tree is
      contained by origin/main; this stale non-terminal projection requires no further
      implementation.'
    created_at: '2026-08-14T07:30:10.055453+00:00'
    selected_ref: origin/main
    selected_sha: 683b5f34a3c30eed0a608cddbd8ffe1c7874ab34
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1207
    target_state: Merged
    evidence_fingerprint: 6a2d89d1b8e58b16d1963ea3fabedd5d634aa38094a37fa6afd43d5930ab07c1
    workflow_revision: null
    selected_ref: origin/main
    selected_sha: 683b5f34a3c30eed0a608cddbd8ffe1c7874ab34
    landing_revision: null
    audit_ids:
    - audit-371f4e17043f
    - audit-0fdf1367d086
    kind: override
    applied: true
    retired_at: '2026-08-14T07:30:19.690314+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-371f4e17043f
    project_id: proj-14849f1b
    task_id: OOMPAH-1207
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a2d89d1b8e58b16d1963ea3fabedd5d634aa38094a37fa6afd43d5930ab07c1
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T02:59:07.813945+00:00'
    eligible_at: '2026-08-13T02:59:07.813945+00:00'
    selected_ref: origin/main
    selected_sha: 683b5f34a3c30eed0a608cddbd8ffe1c7874ab34
    updated_at: '2026-08-14T07:30:19.690256+00:00'
  - version: 1
    audit_id: audit-0fdf1367d086
    project_id: proj-14849f1b
    task_id: OOMPAH-1207
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 6a2d89d1b8e58b16d1963ea3fabedd5d634aa38094a37fa6afd43d5930ab07c1
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T02:59:07.813945+00:00'
    prerequisite_audit_id: audit-371f4e17043f
    selected_ref: origin/main
    selected_sha: 683b5f34a3c30eed0a608cddbd8ffe1c7874ab34
    updated_at: '2026-08-14T07:30:19.690292+00:00'
  attempt_history: []
oompah.lifecycle_revision: 2
---
## Summary

Fix a scheduler deadlock in the durable workflow restart boundary. When ImplementationWorkflowController.reconcile_evaluated() encounters an active event:implementation:imperative job whose action differs from the current fact-derived action, WorkflowJobStore.materialize_event() intentionally preserves that protected job and returns an accepted write without a replacement fact job. The reconciliation report nevertheless counts the fact job as required but not materialized. Universal liveness then remains scan_complete=false/restart_reconstruction_pending=true, and worker admission is permanently deferred even though the imperative retry jobs are already queued. Scope: oompah/implementation_workflow.py and, if needed, the WorkflowEventWrite/proof API in oompah/workflow_jobs.py; preserve generation and protected-lane fencing. Add regression tests in tests/test_implementation_workflow.py and/or tests/test_workflow_runtime.py reproducing restart convergence with a different active imperative action. Acceptance: the active protected imperative job is treated as exact execution authority for reconciliation accounting, restart reconstruction converges, continue_admission_async can drain the job, stale/older fact scans still cannot replace it, and focused workflow tests plus the project gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 02:42
---
Implemented the restart reconstruction fix on branch OOMPAH-1207. Protected imperative implementation jobs now satisfy the current fact decision's materialization obligation, both in implementation reconciliation accounting and universal restart proof. Regression coverage exercises fact reconciliation and two-cut restart liveness. Verification: 324 affected workflow suites passed; terminal-audit mutation scan passed; secret scan passed.
---
author: oompah
created: 2026-08-13 02:59
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 07:30
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Owner convergence: PR #846 merged as 683b5f34a and that landed tree is contained by origin/main; this stale non-terminal projection requires no further implementation.
---
<!-- COMMENTS:END -->
