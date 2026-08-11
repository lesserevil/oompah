---
id: OOMPAH-1081
type: task
status: Archived
priority: null
title: Reject or canonicalize terminal-audit target-state mismatches atomically
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T11:03:28.831065Z'
updated_at: '2026-08-11T11:08:11.133756Z'
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
  creation_marker: 5c9d157e-909c-431f-820b-addd53928270
  request_fingerprint: a8df373a50c836c8eca44a9637323eef8d971132979746803e70789fde43d65d
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-fd5822f7c7ad
    project_id: proj-14849f1b
    task_id: OOMPAH-1081
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 4a9097f0145990d78abb22da61e76ef9c9e7f6520f722168551766fb49a65ccb
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: "Withdrawn before implementation because live metadata disproved the initial\
      \ target-mismatch diagnosis. The accepted Done result was the valid prerequisite\
      \ of a Done\u2192Merged chain; the actual queued-next-stage liveness defect\
      \ is tracked separately with exact evidence."
    created_at: '2026-08-11T11:08:00.811363+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1081
    target_state: Archived
    evidence_fingerprint: 4a9097f0145990d78abb22da61e76ef9c9e7f6520f722168551766fb49a65ccb
    workflow_revision: null
    selected_ref: null
    selected_sha: null
    landing_revision: null
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-11T11:08:09.324881+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-1072. Live reproduction: OOMPAH-1072 was queued for terminal transition to Merged, but auditor audit-00d5d7755c13 submitted PASS with target_state Done. The audit-result API accepted the verdict and returned applied_status In Validation; the task stayed In Validation across a graceful restart despite durable PASS evidence, requiring a project-owner workaround. Scope: bind an audit attempt to its canonical requested terminal state and make result submission either reject a mismatched target_state with an actionable non-mutating error, or ignore/canonicalize the auditor-supplied state to the bound requested state. A PASS must atomically finalize the bound terminal transition or durably stage an idempotent finalization job; it must never accept PASS while leaving a naked In Validation task. Preserve exact attempt/evidence fingerprint, stale-attempt fencing, audit retry/override flows, crash recovery and idempotence. Relevant code: terminal audit result MCP/API handler, TerminalAuditCoordinator/metadata/job stores, TaskTransitionService and restart reconciliation. Tests/acceptance: OOMPAH-1072-shaped Merged request plus auditor target Done cannot be accepted into stranded In Validation; correct PASS finalizes Merged exactly once; injected tracker/store failures recover after restart without duplicate comments/effects; stale/wrong attempts fail closed; focused tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-11 11:07
---
Diagnosis correction before code changes: audit-00d5d7755c13 was the valid bound Done prerequisite in a Done→Merged chain, not a mismatched result. Metadata shows audit-078f5a8faba5 (Merged) remained pending and workflow-job-ce9f7c40... stayed queued at attempts=0 after the Done PASS and across restart. No OOMPAH-1081 code was written. Withdrawing this mis-scoped task and filing the precise chained-stage eligibility/dispatch bug.
---
author: oompah
created: 2026-08-11 11:08
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Withdrawn before implementation because live metadata disproved the initial target-mismatch diagnosis. The accepted Done result was the valid prerequisite of a Done→Merged chain; the actual queued-next-stage liveness defect is tracked separately with exact evidence.
---
<!-- COMMENTS:END -->
