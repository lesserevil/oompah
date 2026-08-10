---
id: OOMPAH-1000
type: bug
status: Open
priority: 1
title: Bind direct-recovery terminal gate identity to the immutable audit revision
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T17:36:32.614914Z'
updated_at: '2026-08-10T17:52:16.564626Z'
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
  creation_marker: o999-terminal-gate-audit-selected-sha-v1
  request_fingerprint: 277a198f28adbc26f867ebadc4659c02b081c3e20661b5b3f8d5bf088cd7fd2e
---
## Summary

Triggered by: OOMPAH-999

Triggered by OOMPAH-999. Problem: a durable terminal-audit attempt was exactly bound to selected_ref and selected_sha 6418a935de7b4aab93a24af4756a54b344463513, but terminal quality-gate evidence recorded an empty head because identity resolution only consumed ordinary issue review/source metadata, which direct recovery tasks may not have. Scope: centralize terminal-gate identity resolution in oompah/orchestrator.py; preserve normal accepted-head authority and, only when it is absent, admit AuditorTargetContract.selected_sha from a freshly reloaded matching pending attempt whose project, task, audit attempt, fingerprint, and state all agree. Resolve branch identity from the same durable staging contract. Change oompah/auditor.py or oompah/terminal_audit.py only if the immutable target contract needs an explicit branch key. selected_sha is identity only and must never imply a passing gate. Tests: add regressions in tests/test_quality_gate.py and tests/test_terminal_audit_observability.py for an OOMPAH-999-shaped audit with no ordinary head; stale fingerprint/attempt, wrong task/project, conflicting head, invalid binding, and changed state must fail closed; OOMPAH-980/OOMPAH-988 review and deleted-branch behavior must remain unchanged; exact SHA without passing evidence must remain full_gate_required. Acceptance: terminal metrics, prompts, and gate lookup use the truthful immutable audit head, all mismatches fail closed, and focused plus complete protected gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

