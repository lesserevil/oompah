---
id: OOMPAH-1081
type: task
status: Open
priority: null
title: Reject or canonicalize terminal-audit target-state mismatches atomically
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-11T11:03:28.831065Z'
updated_at: '2026-08-11T11:03:34.001351Z'
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
---
## Summary

Triggered by: OOMPAH-1072. Live reproduction: OOMPAH-1072 was queued for terminal transition to Merged, but auditor audit-00d5d7755c13 submitted PASS with target_state Done. The audit-result API accepted the verdict and returned applied_status In Validation; the task stayed In Validation across a graceful restart despite durable PASS evidence, requiring a project-owner workaround. Scope: bind an audit attempt to its canonical requested terminal state and make result submission either reject a mismatched target_state with an actionable non-mutating error, or ignore/canonicalize the auditor-supplied state to the bound requested state. A PASS must atomically finalize the bound terminal transition or durably stage an idempotent finalization job; it must never accept PASS while leaving a naked In Validation task. Preserve exact attempt/evidence fingerprint, stale-attempt fencing, audit retry/override flows, crash recovery and idempotence. Relevant code: terminal audit result MCP/API handler, TerminalAuditCoordinator/metadata/job stores, TaskTransitionService and restart reconciliation. Tests/acceptance: OOMPAH-1072-shaped Merged request plus auditor target Done cannot be accepted into stranded In Validation; correct PASS finalizes Merged exactly once; injected tracker/store failures recover after restart without duplicate comments/effects; stale/wrong attempts fail closed; focused tests and protected CI pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

