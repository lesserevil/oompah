---
id: OOMPAH-1002
type: bug
status: In Progress
priority: 1
title: Keep expected bounded terminal-audit continuation out of degraded service health
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T17:51:08.587712Z'
updated_at: '2026-08-10T17:52:56.321762Z'
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
  creation_marker: terminal-audit-bounded-scan-health-canary-v1
  request_fingerprint: e27c950bbdd5a9f653862121b7839a09138c5d69fa61ffe319e96acf827baad6
---
## Summary

Triggered by: OOMPAH-940

Triggered by the live OOMPAH-940 rollout canary on 2026-08-10. A healthy generation with complete workflow liveness, zero current divergence, zero current exhausted jobs, and no actionable alerts failed make workflow-rollout-check solely because TerminalAuditHealth.scan_complete was false while scan_error_count was zero. The same snapshot correctly emitted the informational, action_required=false message 'Terminal-audit health scan is continuing' because the configured bounded cursor deferred ordinary work, yet TerminalAuditHealth.degraded unconditionally treated not scan_complete as degraded and the aggregate service status became non-healthy. Scope: align terminal-audit health severity, aggregate service health, and the rollout gate. An expected bounded continuation with no scan errors, no stale/quarantined/retry-exhausted work, and no other terminal-audit failure must remain informational and must not alone degrade service health or fail the canary. An incomplete scan caused by source/scan errors or accompanied by any real failure must remain fail-closed, actionable, degraded, and canary-failing. Prefer fixing the authoritative TerminalAuditHealth classification rather than adding a display-text exception to scripts/workflow_rollout_check.py; preserve explicit coverage fields so operators can still see scan_complete=false. Relevant files: oompah/terminal_audit_health.py, aggregate health projection in oompah/orchestrator.py/server snapshot if needed, scripts/workflow_rollout_check.py only for contract tests, tests/test_terminal_audit_health.py, tests/test_terminal_audit_observability.py, and tests/test_workflow_rollout_check.py. Tests: bounded continuation with scan_error_count=0 produces the existing info alert but non-degraded service health and passes rollout evaluation; incomplete scan with scan_error_count>0 remains warning/action_required/degraded and fails; stale pending, quarantined, retry-exhausted, transport, policy, configuration, and finalization failures remain degraded regardless of scan state; persistence/restart retains the distinction. Acceptance: the five-minute rollout canary is stable across normal bounded audit cursor continuation without weakening any actual audit-health failure signal, and focused plus complete protected gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 17:52
---
Implementation correction after reviewing OOMPAH-947: preserve the accepted invariant that partial terminal-audit health cuts never claim complete/healthy. Do not change TerminalAuditHealth.degraded to treat scan_complete=false as healthy. Instead make scripts/workflow_rollout_check.py stateful: a sample whose only non-healthy cause is expected bounded audit continuation may be provisional only when terminal_audit.scan_complete=false, scan_error_count=0, every real terminal-audit failure/stale/quarantine/retry count is zero, workflow liveness is complete/healthy, current exhausted/expired/quarantined jobs are zero, topology/rollout evidence is current, and global_alerts is empty. The canary must still require at least one scan_complete=true overall-healthy sample during its configured window and must fail at the deadline if none arrives. Any actionable alert, scan error, real audit failure, other component degradation, or workflow failure remains an immediate failure. Add sequence tests for healthy -> provisional -> healthy pass; provisional -> healthy pass; all-provisional timeout fail; provisional with scan error/real audit failure fail; unrelated degraded health fail. This correction supersedes the description preference to change authoritative TerminalAuditHealth classification.
---
<!-- COMMENTS:END -->
