---
id: OOMPAH-1192
type: task
status: Merged
priority: null
title: Allow durable workflow START to publish runtime before its status transition
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-12T22:43:52.044640Z'
updated_at: '2026-08-14T03:41:12.860499Z'
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
  creation_marker: b17dd9ae-fd84-4b5c-aef8-36b5f938a21d
  request_fingerprint: 3e7a6e731a0e094248063262aa779f0695cd5a17277458467868e8239b1b3a66
oompah.lifecycle_revision: 3
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-647755f57617
    project_id: proj-14849f1b
    task_id: OOMPAH-1192
    digest: b39e46f1de9cadc6a5e155cb59be63904dbc9f78cb89254fb9486690e17e769a
  - version: 1
    audit_id: audit-877e01c56d2b
    project_id: proj-14849f1b
    task_id: OOMPAH-1192
    digest: b39e46f1de9cadc6a5e155cb59be63904dbc9f78cb89254fb9486690e17e769a
  oompah.terminal_override_records:
  - version: 1
    override_id: override-7995cd7306f5
    project_id: proj-14849f1b
    task_id: OOMPAH-1192
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b39e46f1de9cadc6a5e155cb59be63904dbc9f78cb89254fb9486690e17e769a
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Project-owner terminal closure while Oompah scheduling remains intentionally
      paused: PR 840 head 7820d212 merged as 81c63ce5; all Python 3.11, 3.12, and
      3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued
      terminal audits have zero attempts and no recorded error or unresolved review
      blocker.'
    created_at: '2026-08-14T03:40:58.009925+00:00'
    selected_ref: origin/OOMPAH-1192
    selected_sha: 7820d212e4bd7224ec205aae2493ed5f22130fde
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1192
    target_state: Merged
    evidence_fingerprint: b39e46f1de9cadc6a5e155cb59be63904dbc9f78cb89254fb9486690e17e769a
    workflow_revision: null
    selected_ref: origin/OOMPAH-1192
    selected_sha: 7820d212e4bd7224ec205aae2493ed5f22130fde
    landing_revision: null
    audit_ids:
    - audit-647755f57617
    - audit-877e01c56d2b
    kind: override
    applied: true
    retired_at: '2026-08-14T03:41:06.014537+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-647755f57617
    project_id: proj-14849f1b
    task_id: OOMPAH-1192
    target_state: Done
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b39e46f1de9cadc6a5e155cb59be63904dbc9f78cb89254fb9486690e17e769a
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-12T23:03:11.543262+00:00'
    eligible_at: '2026-08-12T23:03:11.543262+00:00'
    selected_ref: origin/OOMPAH-1192
    selected_sha: 7820d212e4bd7224ec205aae2493ed5f22130fde
    updated_at: '2026-08-14T03:41:06.014492+00:00'
  - version: 1
    audit_id: audit-877e01c56d2b
    project_id: proj-14849f1b
    task_id: OOMPAH-1192
    target_state: Merged
    request_state: cancelled
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b39e46f1de9cadc6a5e155cb59be63904dbc9f78cb89254fb9486690e17e769a
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Open
    created_at: '2026-08-12T23:03:11.543262+00:00'
    prerequisite_audit_id: audit-647755f57617
    selected_ref: origin/OOMPAH-1192
    selected_sha: 7820d212e4bd7224ec205aae2493ed5f22130fde
    updated_at: '2026-08-14T03:41:06.014520+00:00'
  attempt_history: []
---
## Summary

Live Trickle scheduling on merged OOMPAH-1189/1190 reaches authenticated native state-branch claim persistence, but every durable ImplementationAction.START aborts before provider admission with durable claim evidence did not converge (status Open expected In Progress, assignment_match true). The durable workflow intentionally calls Orchestrator._dispatch with status_managed_by_workflow=True and applies the journaled Open -> In Progress transition only after execution verification; _dispatch nevertheless enforces In Progress in its immediate post-claim reread, creating an impossible ordering and compensating the assignment back to Open. Scope: make _dispatch validate the correct source-status/assignment evidence when the durable workflow owns the later status transition, while retaining exact assignment, terminal/direct-owner, and stale-status fences; ensure non-workflow dispatches still require In Progress before provider admission. Relevant files: oompah/orchestrator.py, oompah/implementation_workflow_adapter.py, and focused tests. Acceptance: a real durable START from Open persists the exact assignment, publishes one running generation, then transitions to In Progress through the workflow journal; external status/assignment races still abort with zero provider starts; legacy direct dispatch behavior is unchanged; focused tests and complete CI pass; fix merged and deployed before Trickle is resumed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-12 22:44
---
Direct owner is implementing from live evidence. Trickle has been paused to stop retry churn. Observed affected tasks include TRICKLE-123, 124, 131, 132, 134, 135, 137, 119, 121, 122, and 118; all ordinary starts aborted before provider admission and compensation restored Open. The original state-branch transport failure is no longer present.
---
author: oompah
created: 2026-08-12 22:48
---
Implementation committed at 7820d212e and pushed. Focused dispatch/workflow suites pass (90 passed); new regression cases cover workflow-owned source-state admission and external status-race rejection. PR #840 opened with auto-merge armed. Trickle remains paused.
---
author: oompah
created: 2026-08-12 23:03
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-14 03:41
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Project-owner terminal closure while Oompah scheduling remains intentionally paused: PR 840 head 7820d212 merged as 81c63ce5; all Python 3.11, 3.12, and 3.13 CI jobs passed; the merge is included in deployed main 948ef6f; queued terminal audits have zero attempts and no recorded error or unresolved review blocker.
---
author: oompah
created: 2026-08-14 03:41
---
Merged and deployed through PR 840; owner-verified terminal evidence replaces the intentionally unrun paused-project auditor.
---
<!-- COMMENTS:END -->
