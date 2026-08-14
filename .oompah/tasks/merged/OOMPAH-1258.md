---
id: OOMPAH-1258
type: task
status: Merged
priority: null
title: Complete direct epic maintenance through the durable workflow
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-13T22:41:28.315466Z'
updated_at: '2026-08-14T03:43:08.134181Z'
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
  creation_marker: cc0c5a04-711a-4b53-9ccb-aa96ce836044
  request_fingerprint: c9ce64ee590cb20387926be736d3c23fe19e5d785cc955861f8d6da1d7b17b01
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-34e08cda3145
    project_id: proj-14849f1b
    task_id: OOMPAH-1258
    digest: 61674f78694d73f3c6a4a98f80402124d74c8245301a979f60e24af6cb4f2202
  - version: 1
    audit_id: audit-bf14b9b4d11b
    project_id: proj-14849f1b
    task_id: OOMPAH-1258
    digest: 61674f78694d73f3c6a4a98f80402124d74c8245301a979f60e24af6cb4f2202
  oompah.terminal_override_records:
  - version: 1
    override_id: override-8a13d4e570f6
    project_id: proj-14849f1b
    task_id: OOMPAH-1258
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 61674f78694d73f3c6a4a98f80402124d74c8245301a979f60e24af6cb4f2202
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner terminal closure while Oompah scheduling remains intentionally
      paused: PR 875 head 9a02dea4 merged as c72efadf; all Python 3.11, 3.12, and
      3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued
      terminal audits have zero attempts and no recorded error or unresolved review
      blocker.'
    created_at: '2026-08-14T03:42:53.494725+00:00'
    selected_ref: origin/OOMPAH-1258
    selected_sha: 9a02dea4bb32e6f176a63badea7c51550e2f948b
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1258
    target_state: Merged
    evidence_fingerprint: 61674f78694d73f3c6a4a98f80402124d74c8245301a979f60e24af6cb4f2202
    workflow_revision: null
    selected_ref: origin/OOMPAH-1258
    selected_sha: 9a02dea4bb32e6f176a63badea7c51550e2f948b
    landing_revision: null
    audit_ids:
    - audit-34e08cda3145
    - audit-bf14b9b4d11b
    kind: override
    applied: true
    retired_at: '2026-08-14T03:43:01.509595+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-34e08cda3145
    project_id: proj-14849f1b
    task_id: OOMPAH-1258
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 61674f78694d73f3c6a4a98f80402124d74c8245301a979f60e24af6cb4f2202
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T23:46:14.984417+00:00'
    eligible_at: '2026-08-13T23:46:14.984417+00:00'
    selected_ref: origin/OOMPAH-1258
    selected_sha: 9a02dea4bb32e6f176a63badea7c51550e2f948b
    updated_at: '2026-08-14T03:43:01.509551+00:00'
  - version: 1
    audit_id: audit-bf14b9b4d11b
    project_id: proj-14849f1b
    task_id: OOMPAH-1258
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 61674f78694d73f3c6a4a98f80402124d74c8245301a979f60e24af6cb4f2202
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Backlog
    created_at: '2026-08-13T23:46:14.984417+00:00'
    prerequisite_audit_id: audit-34e08cda3145
    selected_ref: origin/OOMPAH-1258
    selected_sha: 9a02dea4bb32e6f176a63badea7c51550e2f948b
    updated_at: '2026-08-14T03:43:01.509577+00:00'
  attempt_history: []
oompah.lifecycle_revision: 2
---
## Summary

Live follow-up to OOMPAH-1257. In all-enforce mode, a recognized direct epic rebase helper can be audited to Done while its exact integration record remains state=ready. The disabled legacy _process_integration_queues sweep is currently the only code that calls complete_direct_epic_maintenance_submission to reconcile the published parent ref, persist maintenance_publication_proven/integrated, cancel the stale ordinary queue row, and converge the parent rebase label. The durable IntegrationWorkflow instead evaluates the Done helper as ordinary landing work and exhausts integration_landing_refresh (live reproducer TRICKLE-141 / parent TRICKLE-130). Implement a task-scoped durable integration action for recognized direct maintenance ready evidence, with exact project/task/branch/head/evidence-generation revalidation and idempotent observation/apply/verification. It must call the existing guarded completion primitive without enabling any project-wide legacy lifecycle writer; supersede the generic landing-refresh generation once proof is durable; reuse already-completed exact audit evidence safely; and preserve fail-closed behavior for spoofed metadata, changed heads/targets, stale jobs, pause, restart, and ordinary queue tasks. Relevant files: oompah/work_decision.py, oompah/integration_workflow.py, workflow action routing/receipts, and focused workflow/integration tests. Required tests: production-shaped noncanonical helper in Ready and Done with state=ready schedules only the maintenance-completion action; action persists integrated proof and parent convergence; restart/replay observes success without repeating unsafe publication; stale/foreign/spoofed generations are rejected; ordinary tasks remain unchanged. Acceptance: after deployment TRICKLE-141 naturally converges without SQLite/task-ledger edits, TRICKLE-130 loses stale rebasing state, no retry.exhausted alert remains for the helper, and only Trickle remains resumed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-13 22:41
---
Claimed for direct implementation after live all-enforce reproduction: TRICKLE-141 is correctly classified as a noncanonical direct helper, but state=ready is routed to generic integration_landing_refresh because the only ready-to-proven conversion remains in the disabled legacy project sweep. Implementing a task-scoped durable maintenance-completion action; no project-wide writer will be re-enabled.
---
author: oompah
created: 2026-08-13 23:11
---
Implementation underway on branch OOMPAH-1258. Added a durable direct_epic_maintenance_completion integration action selected for exact Ready/Done helpers instead of generic landing refresh; it revalidates project/task/status/branch/head/evidence under the shared task mutex, calls the existing guarded completion primitive, observes proof plus parent rebase-state/label convergence, and handles the post-cancel/pre-label crash boundary idempotently. Validation: 729 focused workflow/runtime/orchestrator tests passed; 424 direct affected tests passed; terminal mutation scan 21/21; diff check clean. Independent review in progress.
---
author: oompah
created: 2026-08-13 23:46
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 00:38
---
Live acceptance is complete after OOMPAH-1259 deployed. The durable direct_epic_maintenance_completion job for TRICKLE-141 is completed, TRICKLE-141 is Done, and parent TRICKLE-130 carries epic:rebased. Restart reconstruction now converges with pending=false, proving the completion can survive and recover across restart.
---
author: oompah
created: 2026-08-14 03:43
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner terminal closure while Oompah scheduling remains intentionally paused: PR 875 head 9a02dea4 merged as c72efadf; all Python 3.11, 3.12, and 3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued terminal audits have zero attempts and no recorded error or unresolved review blocker.
---
author: oompah
created: 2026-08-14 03:43
---
Merged and deployed through PR 875; owner-verified terminal evidence replaces the intentionally unrun paused-project auditor.
---
<!-- COMMENTS:END -->
