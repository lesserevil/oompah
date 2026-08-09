---
id: OOMPAH-969
type: task
status: Done
priority: null
title: Preserve fast workflow admission under continuous ordinary events
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T19:25:38.748132Z'
updated_at: '2026-08-09T20:07:11.079646Z'
work_branch: OOMPAH-969
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: standalone
  task_branch: OOMPAH-969
  head_sha: ff13d997972b56cbab1b4202cc0eb9f62445cd1b
  submitted_at: '2026-08-09T19:57:42.854981+00:00'
  updated_at: '2026-08-09T19:57:42.854981+00:00'
oompah.work_branch: OOMPAH-969
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-0f553a9141b1
    project_id: proj-14849f1b
    task_id: OOMPAH-969
    digest: 73c65f709aa2a61069c82dbc5fbc961e1575e2b4a7d18b6a4a2273b4a85236c7
  - version: 1
    audit_id: audit-a5f59964669f
    project_id: proj-14849f1b
    task_id: OOMPAH-969
    digest: 73c65f709aa2a61069c82dbc5fbc961e1575e2b4a7d18b6a4a2273b4a85236c7
  oompah.terminal_override_records:
  - version: 1
    override_id: override-98b16082c871
    project_id: proj-14849f1b
    task_id: OOMPAH-969
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 73c65f709aa2a61069c82dbc5fbc961e1575e2b4a7d18b6a4a2273b4a85236c7
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: '[REDACTED]'
    created_at: '2026-08-09T20:07:07.015118+00:00'
    selected_ref: ff13d997972b56cbab1b4202cc0eb9f62445cd1b
    selected_sha: ff13d997972b56cbab1b4202cc0eb9f62445cd1b
    applied: false
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0f553a9141b1
    project_id: proj-14849f1b
    task_id: OOMPAH-969
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 73c65f709aa2a61069c82dbc5fbc961e1575e2b4a7d18b6a4a2273b4a85236c7
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T20:06:27.175305+00:00'
    selected_ref: ff13d997972b56cbab1b4202cc0eb9f62445cd1b
    selected_sha: ff13d997972b56cbab1b4202cc0eb9f62445cd1b
  - version: 1
    audit_id: audit-a5f59964669f
    project_id: proj-14849f1b
    task_id: OOMPAH-969
    target_state: Merged
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 73c65f709aa2a61069c82dbc5fbc961e1575e2b4a7d18b6a4a2273b4a85236c7
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: NVShawn
      source: forge
    previous_state: Ready to Integrate
    created_at: '2026-08-09T20:06:27.175305+00:00'
    selected_ref: ff13d997972b56cbab1b4202cc0eb9f62445cd1b
    selected_sha: ff13d997972b56cbab1b4202cc0eb9f62445cd1b
  attempt_history: []
---
## Summary

Regression of OOMPAH-959 observed live on 2026-08-09 while integrating OOMPAH-967. Durable workflow effect completion posts WORKFLOW_ADMISSION, but the dispatch loop allows a coalesced ordinary refresh/webhook event to subsume that admission wake into a full world reconciliation. With full ticks taking 178–188 seconds, all three shared workflow slots remained idle for roughly 165–201 seconds despite more than 76 due decision rows; OOMPAH-967 integration_attempt remained queued with attempts=0 for over 21 minutes. OOMPAH-955 reserved control-lane admission still worked, so this is specifically loss of fair/prompt shared admission continuation under continuous ordinary events.\n\nImplementation scope: preserve an independent bounded admission turn when completion requests WORKFLOW_ADMISSION even if ordinary events are already/coincidentally queued; keep event coalescing, single-owner orchestration, pause/quiesce semantics, control-slot reservation, and bounded scan behavior; do not create a busy loop or starve ordinary reconciliation. Relevant code: orchestrator dispatch/event coalescing around OOMPAH-959 and tests including test_ordinary_event_subsumes_coalesced_admission_wake.\n\nRequired tests: reproduce continuous ordinary events while shared jobs finish and prove due replacements are admitted promptly without waiting for the next full world scan; prove ordinary reconciliation still runs fairly; prove pause/quiesce prevents admission; preserve control-lane isolation and no-spin behavior. Acceptance: live-equivalent queued effects drain through prompt bounded continuations, shared slots do not remain idle behind a multi-minute full scan solely because an ordinary event subsumed admission, focused orchestrator/workflow tests pass, and protected CI passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 19:26
---
Accepted for direct-owner implementation. Live evidence confirms the shared admission continuation is starved by ordinary-event coalescing while the reserved control lane remains correct.
---
author: oompah
created: 2026-08-09 19:41
---
Implementation is pushed at exact head e513c7da36eaf240723a645d72147af2b7bb9d90. Workflow effect completion now wakes a single independently coalesced scheduler-loop admission owner, so shared capacity refills while ordinary world reconciliation remains in flight; ordinary fairness, stale-cut fallback, pause/quiesce/accepting fences, control isolation, and graceful drain remain intact. Validation: 235 focused orchestrator/runtime tests passed; changed-line Ruff and diff checks are clean. Holding final submit until the OOMPAH-968/OOMPAH-970 base settles and independent review completes.
---
author: oompah
created: 2026-08-09 19:57
---
Final rebased head ff13d997972b56cbab1b4202cc0eb9f62445cd1b is pushed on merged OOMPAH-968/OOMPAH-970 main. Stable patch-id is unchanged from independently accepted e513c7da3. Post-rebase validation: 240 orchestrator/event-loop/workflow-runtime tests passed; diff check and worktree are clean. Touched-file Ruff output contains only the pre-existing baseline findings documented by the implementer; changed lines are clean.
---
author: oompah
created: 2026-08-09 19:57
---
Preserve prompt workflow-effect admission during multi-minute ordinary reconciliation using one coalesced, fenced scheduler-loop owner. Final head ff13d997972b56cbab1b4202cc0eb9f62445cd1b; 240 post-rebase tests and independent review are green.
---
author: oompah
created: 2026-08-09 19:58
---
Branch quality gate blocked review creation.

Branch: `OOMPAH-969`
Target: `main`
Head: `ff13d997972b56cbab1b4202cc0eb9f62445cd1b`
Command: `make test`
Result: `infrastructure_error`
Process: ended without subprocess exit evidence

Infrastructure action required: repair or replace the operator-owned quality-gate runtime. No candidate CI-fix status was applied because the candidate command did not run.

Output tail:
```text
Trusted quality-gate runtime corruption detected; candidate CI was not run: trusted editable source mapping is inconsistent: expected one of ['/home/shedwards/src/oompah'] or immutable candidate /home/shedwards/.oompah/tmp/oompah-quality-gate-jcls2jrm/run/workspace; actual /home/shedwards/src/oompah-967. Repair or replace the service test runtime before rerunning the branch gate.
```
---
author: oompah
created: 2026-08-09 20:06
---
Queued for terminal transition to Merged. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
