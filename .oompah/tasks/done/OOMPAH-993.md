---
id: OOMPAH-993
type: bug
status: Done
priority: 1
title: Make standalone delivery mutations lock-safe across thread offloads
parent: OOMPAH-992
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:52:26.512449Z'
updated_at: '2026-08-10T18:59:10.797152Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-54fa91e7a4ae
    project_id: proj-14849f1b
    task_id: OOMPAH-993
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 15613530be903765a84644ff8615657d25e7110b967f7a4fb7e40791dce9fbce
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'PR #798 merged as 2ab880be5; parent OOMPAH-992 is authoritatively terminal;
      contained 9c595c5b2 is stable-patch-identical to reviewed OOMPAH-993 head 03c67abb8.
      Recording child completion as Done because shared-child Merged requires a parent
      review record that this direct-owner integration intentionally did not create.'
    created_at: '2026-08-10T15:40:01.330912+00:00'
    selected_ref: origin/OOMPAH-993
    selected_sha: 03c67abb83d15442bc1e72862d632d3b2108de51
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-993
    target_state: Done
    evidence_fingerprint: 15613530be903765a84644ff8615657d25e7110b967f7a4fb7e40791dce9fbce
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T15:40:11.024819+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: 'PR #798 merged as 2ab880be5; reviewed OOMPAH-993 integration commit 9c595c5b215291c40f14db052d186490622085d8
      is contained in main and no standalone landing receipt exists. Retain this completed
      Done record as immutable terminal provenance.'
    marked_at: '2026-08-10T18:59:09.347437+00:00'
    updated_at: '2026-08-10T18:59:09.347437+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: 'PR #798 merged as 2ab880be5; reviewed OOMPAH-993 integration commit
        9c595c5b215291c40f14db052d186490622085d8 is contained in main and no standalone
        landing receipt exists. Retain this completed Done record as immutable terminal
        provenance.'
      recorded_at: '2026-08-10T18:59:09.347437+00:00'
      authority_generation: 0
    actor:
      version: 1
      identity: oompah-cli
      source: api
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Replace the lock-spanning standalone-delivery mutation path with admitted, generation-bound operations so TaskTransitionService and tracker I/O never run while the project write lock or standalone delivery authority lock is held. Reproduce the quality-gate failure deadlock against ProvenanceGuardedTracker, preserve revocation and ABA/supersession semantics, and add focused tests proving the transition completes to Needs CI Fix and tracker callbacks execute without the project lock.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 11:25
---
Implemented and pushed commit 03c67abb8 on branch OOMPAH-993. Standalone tracker/forge effects now use exact generation-bound admission without retaining project, authority, lifecycle, or issue locks across external callbacks. Busy terminal revocation marks the admitted generation pending and TaskTransitionService journals a retryable transition; replacement claims are deferred to preserve ABA fencing. Irreversible review creation remains admitted through capacity/metadata/In Review publication, preventing orphan PRs. Coverage includes the exact ProvenanceGuardedTracker quality-gate failure transition to Needs CI Fix, revocation/replacement races, terminal-during-create no-orphan publication, lock observations, all terminal revocation entry points, and retry journaling. Verification: standalone delivery 84 passed; task transition service 86 passed; terminal coordinator 228 passed; focused quality-gate 3 passed; make terminal-audit-scan passed.
---
author: oompah
created: 2026-08-10 11:25
---
Submission is currently blocked by the tracker Git-authority prerequisite: origin/epic-OOMPAH-992 is not published. The completed task branch itself is pushed and clean at 03c67abb8; submit OOMPAH-993 after the parent integration branch is published.
---
author: oompah
created: 2026-08-10 11:37
---
Exact child head 03c67abb83d15442bc1e72862d632d3b2108de51 was reviewed and integrated into shared OOMPAH-989 as 9c595c5b2. Combined review added cross-child authority fixes at e09ad2e26, including pending gate-result fencing, durable capacity retention for a forge review returned after authority loss, and a final contained-no-op authority CAS. The combined focused suite passes 458 tests. The clean pushed child worktree has been pruned; the child remains In Progress pending the shared PR landing.
---
author: oompah
created: 2026-08-10 15:40
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: PR #798 merged as 2ab880be5; parent OOMPAH-992 is authoritatively terminal; contained 9c595c5b2 is stable-patch-identical to reviewed OOMPAH-993 head 03c67abb8. Recording child completion as Done because shared-child Merged requires a parent review record that this direct-owner integration intentionally did not create.
---
<!-- COMMENTS:END -->
