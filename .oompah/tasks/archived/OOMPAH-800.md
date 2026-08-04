---
id: OOMPAH-800
type: task
status: Archived
priority: 1
title: Define stable workflow reason codes and liveness SLOs
parent: OOMPAH-764
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T14:00:48.571071Z'
updated_at: '2026-08-04T14:02:32.970400Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-a8fdbf2f5109
    project_id: proj-14849f1b
    task_id: OOMPAH-800
    target_state: Archived
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 0648aef33ed1653e1f7a3ea6a6047a75c7607ff80feb010be2775483c308302f
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Accidental duplicate created while verifying concurrently submitted task-creation
      requests; canonical task is OOMPAH-773.
    created_at: '2026-08-04T14:02:18.806113+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-800
    target_state: Archived
    evidence_fingerprint: 0648aef33ed1653e1f7a3ea6a6047a75c7607ff80feb010be2775483c308302f
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-04T14:02:26.731062+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Define versioned reason codes and SLOs for Open, In Progress, Ready, In Validation, In Review, recovery, and restart convergence. Specify owner, evidence, reassessment deadline, action_required, severity, and remedy without message parsing. Add schema/docs/tests for serialization, forward compatibility, severity mapping, and total nonterminal coverage. Acceptance: normal recovery is informational and every nonterminal decision has a bounded reassessment policy.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-04 14:02
---
Override by oompah-cli: terminal transition to Archived applied by project owner.

Reason: Accidental duplicate created while verifying concurrently submitted task-creation requests; canonical task is OOMPAH-773.
---
author: oompah
created: 2026-08-04 14:02
---
Archived accidental duplicate; use OOMPAH-773.
---
<!-- COMMENTS:END -->
