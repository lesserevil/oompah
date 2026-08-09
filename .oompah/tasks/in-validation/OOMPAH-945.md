---
id: OOMPAH-945
type: bug
status: In Validation
priority: 1
title: Unify terminal transition guards with exact-current work decisions
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:46.122749Z'
updated_at: '2026-08-09T12:53:42.895802Z'
work_branch: OOMPAH-945
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.integration:
  version: 2
  state: ready
  attempts: 0
  mode: queue
  task_branch: OOMPAH-945
  base_branch: epic-OOMPAH-940
  base_sha: b7e7d9509a4e6025b48c54336098acef2dda4986
  head_sha: 748fd1da7f5c3c97e9ac9695092c477412ffea2b
  submitted_at: '2026-08-09T10:03:11.620082+00:00'
  updated_at: '2026-08-09T10:03:11.620082+00:00'
oompah.work_branch: OOMPAH-945
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-f8c3a0d0da6a
    project_id: proj-14849f1b
    task_id: OOMPAH-945
    digest: b5832f95f60866a606034ed5b62fdf3147df4fcbd413f40d912ebc6b363bdd91
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f8c3a0d0da6a
    project_id: proj-14849f1b
    task_id: OOMPAH-945
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: b5832f95f60866a606034ed5b62fdf3147df4fcbd413f40d912ebc6b363bdd91
    attempts: []
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:53:34.839367+00:00'
    selected_ref: 748fd1da7f5c3c97e9ac9695092c477412ffea2b
    selected_sha: 748fd1da7f5c3c97e9ac9695092c477412ffea2b
  attempt_history: []
---
## Summary

Complete liveness generation 260 projects OOMPAH-476 and OOMPAH-763 as disposition=terminal with reason terminal.immediate_target_landing_proven and zero divergence, yet set-status Merged rejects the child because its parent cannot be verified and rejects the epic because immediate-target evidence no longer authorizes auto-close. Scope: remove the semantic drift between decision projection and mutation guard by carrying/verifying an exact current decision/evidence generation through TaskTransitionService/owner override and automatic rollup. A terminal decision must either be executable under the same authority or must not be published as terminal. Preserve topology ordering, stale-generation fencing, owner authentication, and fail-closed unknown evidence. Tests: child/epic cases above, decision changes between evaluation and commit, parent-not-yet-landed sequencing, malicious/stale decision injection, and restart. Acceptance: exact-current terminal decisions apply once or return an explicit stale retry—not a contradictory policy rejection—and non-terminal decisions cannot bypass guards.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 09:10
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
author: oompah
created: 2026-08-09 09:11
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
author: oompah
created: 2026-08-09 09:25
---
Implemented the two reproduced authority splits in the isolated OOMPAH-945 worktree. Terminal API ownership refresh now restores the canonical native-tracker project scope and rejects explicit cross-project refreshes before staging. Done-epic decisions and lifecycle guards now share one containment-derived immediate-target landing selector, so child landings cannot falsely authorize epic auto-close when task branch metadata is absent. Focused decision/API/runtime/epic/integration/transition/audit coverage is green: 826 passed. Terminal mutation scan and secret scan pass; preparing the exact commit for publication.
---
author: oompah
created: 2026-08-09 09:27
---
Exact implementation commit 395ce9938 is pushed on origin/OOMPAH-945 and the worktree is clean/up to date. Normal  was attempted and correctly failed closed because the declared immediate target origin/epic-OOMPAH-940 is not yet published. No main-target PR or topology bypass was created. Resubmit after the parent epic target is published/composed.
---
author: oompah
created: 2026-08-09 09:27
---
Clarification: the normal Oompah submission command was attempted and correctly failed closed because the declared immediate target origin/epic-OOMPAH-940 is not yet published. Commit 395ce9938 remains clean and pushed; resubmit after the parent epic target is published/composed.
---
author: oompah
created: 2026-08-09 09:28
---
Published 395ce9938: canonicalize terminal API refresh scope and share containment-derived Done-epic landing authority between WorkDecision and lifecycle guards. Regressions cover native scope restoration, cross-project refresh rejection, unrelated child landing exclusion, and missing/malformed containment. Verification: 826 focused tests passed; terminal mutation and secret scans passed.
---
author: oompah
created: 2026-08-09 10:03
---
Independent review found and fixed a refresh-boundary identity substitution: a same-project or native project-less response for a different identifier could be rebound to the requested project and reach the coordinator under the wrong task lock. Refresh now requires exact id and identifier before project rebinding. Adversarial cases verify the original lock, no coordinator call, no project mutation, and dispatch-fence rollback. Full terminal-interface suite: 80 passed. Pushed 748fd1da7f5c3c97e9ac9695092c477412ffea2b.
---
author: oompah
created: 2026-08-09 10:03
---
Added exact refreshed task-identity fencing before terminal project rebinding/coordinator use, with same-project and project-less wrong-identifier regressions; focused checks pass.
---
author: oompah
created: 2026-08-09 12:53
---
Reconciled the in-flight integration deadlock: the accepted task commits are authoritatively contained in origin/epic-OOMPAH-940, so the exhausted administrative integration job is obsolete. Advancing to terminal validation while OOMPAH-958 fixes the systemic lease contract.
---
author: oompah
created: 2026-08-09 12:53
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
