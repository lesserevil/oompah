---
id: OOMPAH-1078
type: task
status: In Validation
priority: null
title: Prevent manual In Validation transitions from stranding terminal audits
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T10:13:51.547647Z'
updated_at: '2026-08-11T10:50:03.917092Z'
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
  creation_marker: fb2a09ae-ea46-4667-bd75-8a9f367c2db3
  request_fingerprint: d17b7df2e7e113a319d6343a89d928aaeb0be8479b7cfddbb5a52132b5d87d97
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-18237c837d61
    project_id: proj-14849f1b
    task_id: OOMPAH-1078
    digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
  - version: 1
    audit_id: audit-4dfa2cf5c0b5
    project_id: proj-14849f1b
    task_id: OOMPAH-1078
    digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-18237c837d61
    project_id: proj-14849f1b
    task_id: OOMPAH-1078
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-11T10:49:57.906153+00:00'
    selected_ref: origin/OOMPAH-1078
    selected_sha: 9c78b999f9b8eeddda14e2c783ea01a688543325
  - version: 1
    audit_id: audit-4dfa2cf5c0b5
    project_id: proj-14849f1b
    task_id: OOMPAH-1078
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: fb7fe1d32d9e1c5ac12f5a590f2393ba9621958bcf9103d1c5f4b625aee929d0
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: In Progress
    created_at: '2026-08-11T10:49:57.906153+00:00'
    selected_ref: origin/OOMPAH-1078
    selected_sha: 9c78b999f9b8eeddda14e2c783ea01a688543325
  attempt_history: []
---
## Summary

Live regression observed 2026-08-11 on merged build 4be80277a: an authenticated direct owner ran 'oompah task set-status OOMPAH-1077 In Validation' after its shared implementation had merged. The API accepted the nonterminal status and retired the owner claim, but did not atomically stage terminal-audit metadata or a durable terminal_audit job. Subsequent complete workflow publications reported reason_code=evidence.terminal_audit_missing, required_recovery_count=6/materialized_recovery_count=5, no active_job_id for OOMPAH-1077, restart reconstruction remained incomplete, and otherwise valid auditors could not dispatch. Implementation scope: make direct API/CLI/dashboard In Validation transitions impossible to strand. Either reject In Validation as a coordinator-owned status unless an exact audit request/delivery evidence is atomically staged, or route the request through the canonical terminal-audit coordinator transaction. Preserve idempotency, project-owner authentication, exact branch/head/provenance requirements, existing submit and terminal override flows, and rollback on staging failure. Relevant code: API task status route, TaskTransitionService/terminal audit staging, CLI set-status behavior, workflow runtime materialization. Required tests: direct In Progress->In Validation without audit evidence cannot commit a naked status; an authorized canonical staging path writes status plus audit metadata/job atomically; injected job-store/tracker failures leave the original status/claim recoverable; retries are idempotent; dashboard/CLI error is actionable; restart liveness never observes In Validation with missing audit materialization solely from this route. Acceptance: the reproduced OOMPAH-1077 sequence is rejected or atomically produces a pending audit, required/materialized recovery counts remain equal, focused API/transition/audit/runtime tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 10:26
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-1078`
Target: `main`
Head: `unknown`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Candidate CI was not run because the submitted review branch tip is unavailable in the managed repository.
```
---
author: oompah
created: 2026-08-11 10:50
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
