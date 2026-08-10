---
id: OOMPAH-1002
type: bug
status: Merged
priority: 1
title: Keep expected bounded terminal-audit continuation out of degraded service health
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T17:51:08.587712Z'
updated_at: '2026-08-10T18:40:15.264527Z'
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
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-429183d672c2
    project_id: proj-14849f1b
    task_id: OOMPAH-1002
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: e90a4c968e025127c8fc871e44d7a600a588142200124c6f75b2ecdcd7983f83
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'Exact implementation 7cfcf162352a308c0cbabb18f617a9d688641d7b is contained
      in protected merge 8eac2ae5097e84840d6b07fe965b37224c0f7960 via PR #800; combined
      exact head 017956bd637bfd3dd9124396fef394b439f47d6a passed the complete local
      Makefile gate and protected Python 3.11/3.12/3.13 CI, with independent adversarial
      approval.'
    created_at: '2026-08-10T18:39:54.947426+00:00'
    selected_ref: origin/OOMPAH-1002
    selected_sha: 7cfcf162352a308c0cbabb18f617a9d688641d7b
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-1002
    target_state: Merged
    evidence_fingerprint: e90a4c968e025127c8fc871e44d7a600a588142200124c6f75b2ecdcd7983f83
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T18:40:07.898486+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
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
author: oompah
created: 2026-08-10 18:02
---
Implementation is pushed for independent review at exact head 7cfcf162352a308c0cbabb18f617a9d688641d7b on origin/OOMPAH-1002. The canary preserves fail-closed TerminalAuditHealth semantics, treats only exact machine-verified budget-deferred continuation samples as provisional, requires at least one complete healthy terminal-audit sample during the configured window, and fails --once plus every scan/audit/workflow/unrelated degradation. Validation: 36 rollout-canary tests passed; 165 combined rollout and terminal-audit health/API/observability tests passed; Ruff, py_compile, git diff check, make terminal-audit-scan (20/20), make check-secrets, and commit hooks passed. Branch is clean and synchronized. Task intentionally remains In Progress and unsubmitted pending independent review.
---
author: oompah
created: 2026-08-10 18:20
---
Protected recovery candidate: PR #800 carries exact OOMPAH-1002 commit 7cfcf162352a308c0cbabb18f617a9d688641d7b in combined head 017956bd637bfd3dd9124396fef394b439f47d6a. Clean combined focused result: 426 passed; full Makefile gate, protected Python 3.11/3.12/3.13 CI, and independent adversarial review are running on that exact head.
---
author: oompah
created: 2026-08-10 18:40
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: Exact implementation 7cfcf162352a308c0cbabb18f617a9d688641d7b is contained in protected merge 8eac2ae5097e84840d6b07fe965b37224c0f7960 via PR #800; combined exact head 017956bd637bfd3dd9124396fef394b439f47d6a passed the complete local Makefile gate and protected Python 3.11/3.12/3.13 CI, with independent adversarial approval.
---
author: oompah
created: 2026-08-10 18:40
---
Merged through protected PR #800. Exact combined verification: 19,520 passed, 7 skipped, 2 xfailed locally; protected Python 3.11/3.12/3.13 jobs passed; independent review approved. Deployed in server revision 8eac2ae5097e84840d6b07fe965b37224c0f7960.
---
<!-- COMMENTS:END -->
