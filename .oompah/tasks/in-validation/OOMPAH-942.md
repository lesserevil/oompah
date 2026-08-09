---
id: OOMPAH-942
type: bug
status: In Validation
priority: 1
title: Backfill trusted terminal-parent heads for pruned epic targets
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:26.152660Z'
updated_at: '2026-08-09T14:02:17.142146Z'
work_branch: OOMPAH-942
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
  task_branch: OOMPAH-942
  base_branch: epic-OOMPAH-940
  base_sha: b7e7d9509a4e6025b48c54336098acef2dda4986
  head_sha: dcda220c225eef11f4704f61cade067d609e2da9
  submitted_at: '2026-08-09T10:04:18.080825+00:00'
  updated_at: '2026-08-09T10:04:18.080825+00:00'
oompah.work_branch: OOMPAH-942
oompah.terminal_audit:
  queued_comment_posted: true
  oompah.terminal_audit_tracker_projections:
  - version: 1
    audit_id: audit-b8deaf092ff9
    project_id: proj-14849f1b
    task_id: OOMPAH-942
    digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-b8deaf092ff9
    project_id: proj-14849f1b
    task_id: OOMPAH-942
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
    attempts:
    - version: 1
      attempt_id: attempt-e3e223790931
      target_state: Done
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
      created_at: '2026-08-09T14:02:05.192902+00:00'
      provider_id: prov-651d553c
      model: haiku
      started_at: '2026-08-09T14:02:05.192902+00:00'
      branch_key: OOMPAH-942
      selected_ref: dcda220c225eef11f4704f61cade067d609e2da9
      selected_sha: dcda220c225eef11f4704f61cade067d609e2da9
    source_generation: 1
    requested_by:
      version: 1
      identity: oompah-cli
      source: api
    previous_state: Ready to Integrate
    created_at: '2026-08-09T12:52:43.120907+00:00'
    selected_ref: dcda220c225eef11f4704f61cade067d609e2da9
    selected_sha: dcda220c225eef11f4704f61cade067d609e2da9
    updated_at: '2026-08-09T14:02:05.192902+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-e3e223790931
    target_state: Done
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: cca0f60722c8c72ed4ad68084440108d7429500afdee93d32f9d1ea141ddae8e
    created_at: '2026-08-09T14:02:05.192902+00:00'
    provider_id: prov-651d553c
    model: haiku
    started_at: '2026-08-09T14:02:05.192902+00:00'
    branch_key: OOMPAH-942
    selected_ref: dcda220c225eef11f4704f61cade067d609e2da9
    selected_sha: dcda220c225eef11f4704f61cade067d609e2da9
---
## Summary

Fourteen resolver-shaped legacy child rows have exact source authority but target pruned epic refs; terminal parents such as OOMPAH-460/585/586/587/588/619 have no accepted exact head, so exact landing evidence remains unavailable. Scope: define and persist a one-time/restart-safe backfill from authoritative parent integration receipts, accepted terminal audit provenance, or exact forge landing evidence; never infer from branch names or current main. Feed the resulting immutable accepted parent head into IntegrationLandingRequestResolver/GitLandingCollector. Tests: each authoritative source, missing/ambiguous/conflicting evidence, pruned branch, restart idempotence, and no mutation of historical jobs. Acceptance: qualifying children prove ancestry/complete patch equivalence against the accepted parent head; unknown parents remain actionable and fail closed.

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
created: 2026-08-09 09:32
---
Implemented/pushed 1b50116ce. Terminal-parent exact heads now backfill from existing immutable landing facts, integrated queue receipts, exact completed audit bindings, or route-matching merged-review heads; the selected proof is persisted before child use and ambiguity, wrong targets, malformed authority, or persistence failure remain fail-closed. Focused integration/runtime result: 153 passed; targeted undefined-name lint passed.
---
author: oompah
created: 2026-08-09 09:32
---
Backfilled and persisted exact terminal-parent heads with fail-closed legacy authority selection; 153 focused tests pass.
---
author: oompah
created: 2026-08-09 09:54
---
Independent review found and fixed a source-authority gap before integration: exact terminal-audit parent backfill now requires the persisted audit binding to match the parent source branch (or an equal immutable revision), and malformed or wrong-ref authority blocks lower-priority fallback. Added a wrong-source fail-closed regression. Verification: 154 integration/runtime tests passed; mutation and secret scans passed.
---
author: oompah
created: 2026-08-09 09:54
---
Backfilled trusted terminal-parent heads only from exact route-bound authority; independent review fix binds terminal-audit proof to the parent source branch. 154 focused tests pass.
---
author: oompah
created: 2026-08-09 09:55
---
Backfilled trusted terminal-parent heads only from exact route-bound authority; independent review fix binds terminal-audit proof to the parent source branch. Exact head 53799805c; 154 focused tests pass.
---
author: oompah
created: 2026-08-09 10:04
---
Second independent review completed before integration. Fixed two additional authority gaps: terminal-audit parent receipts must match the current canonical issue evidence fingerprint, and simultaneous queue/audit/forge exact receipts must agree on one revision before any backfill is persisted. Added stale pre-edit audit and cross-authority conflict regressions. Verification: 156 integration/runtime tests passed; mutation/secret scans and targeted Ruff passed. Exact head dcda220c2.
---
author: oompah
created: 2026-08-09 10:04
---
Persist only one exact route-bound terminal-parent head after current-fingerprint and cross-authority agreement. Exact head dcda220c2; 156 focused tests pass.
---
author: oompah
created: 2026-08-09 12:52
---
Reconciled the in-flight integration deadlock: the accepted task commits are authoritatively contained in origin/epic-OOMPAH-940, so the exhausted administrative integration job is obsolete. Advancing to terminal validation while OOMPAH-958 fixes the systemic lease contract.
---
author: oompah
created: 2026-08-09 12:52
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
author: oompah
created: 2026-08-09 14:02
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/haiku)
---
author: oompah
created: 2026-08-09 14:02
---
Focus: Completion Auditor
---
<!-- COMMENTS:END -->
