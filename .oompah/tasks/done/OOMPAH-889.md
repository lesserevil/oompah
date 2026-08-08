---
id: OOMPAH-889
type: task
status: Done
priority: null
title: Make Done-only maintenance repair survive native parent rollup
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-07T13:16:12.155503Z'
updated_at: '2026-08-08T16:27:04.674461Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-d4c51e7350d8
    project_id: proj-14849f1b
    task_id: OOMPAH-889
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 36fb7a4069f71853f22ad8db6876fce0cfa9bb68578b8b778a865673019cf1f3
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:26:54.183027+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-889
    target_state: Done
    evidence_fingerprint: 36fb7a4069f71853f22ad8db6876fce0cfa9bb68578b8b778a865673019cf1f3
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:27:03.083240+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Live recurrence after merged OOMPAH-725, OOMPAH-825, and OOMPAH-829: OOMPAH-660 remains Merged while its lifecycle row is exhausted after five attempts with lifecycle_repair_not_applied. The classifier correctly says this auto-filed epic rebase helper's successful terminal target is Done. OOMPAH-829 recognizes the exact ab40139d2035↔62954f9b5fdc legacy fingerprint pair and checkpoints the repair, but the native tracker write does not remain applied; repeated authenticated owner Done overrides return HTTP 409 evidence_fingerprint_mismatch against the active historical Done record. Implementation scope: trace the native Markdown parent/child rollup and terminal-metadata transaction after the lifecycle repair; ensure a structurally Done-only maintenance child is excluded from generic parent-landed Merged promotion, or serialize the authoritative Done repair so the rollup cannot immediately overwrite it. Preserve ordinary child Merged convergence after parent landing, exact owner-override stale-evidence checks, and the bounded OOMPAH-829 legacy equivalence fence. Rearm an exhausted lifecycle row when the deployed repair version or authoritative rollup exclusion changes, then finalize and retire its incompatible Merged metadata atomically. Relevant code: native Markdown tracker child/epic rollup hooks, TerminalAuditEnforcement locked lifecycle repair and intent recovery, TerminalTransitionCoordinator override fingerprint matching, and OOMPAH-725/O825/O829 regressions. Required tests: exact production-shaped OOMPAH-660 metadata reaches and stays Done across repeated tracker refresh, parent rollup, restart, and concurrent reconciliation; an authenticated owner Done repair cannot be rejected solely because the current incompatible Merged projection differs from the matching authorized legacy Done evidence; OOMPAH-662 current-match control; ordinary landed children still reach Merged; tampered fingerprints and genuine stale evidence fail closed. Acceptance: without editing task files or service_state, deployed code converges OOMPAH-660 to Done, lifecycle exhausted=0/action_required=false, and repeated ticks cannot regress it to Merged; focused lifecycle/coordinator/native-tracker tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-07 13:16
---
Held in Backlog only until OOMPAH-877 publishes the already-repaired shared epic head. Opening it during the live epic rebase would branch from stale authority and create avoidable integration conflict; promote it immediately after that exact CAS push. No manual task/state-file workaround was applied because the native parent-rollup overwrite is the bug under test.
---
author: oompah
created: 2026-08-07 13:34
---
Additional live recurrence: OOMPAH-764 is a nested epic with all canonical children terminal and stale PR #742 closed. Stale review reconciliation regressed it from audited Done to In Review. Three consecutive authenticated owner Done overrides were rejected with evidence-fingerprint mismatch even after fresh reads, so this is not ordinary request staleness; native epic rollup/metadata writes prevent the exact maintenance terminal repair from committing. Add OOMPAH-764 to the regression corpus and prove the repaired terminal status survives nested-parent rollup/review reconciliation.
---
author: oompah
created: 2026-08-08 16:27
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope is contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
