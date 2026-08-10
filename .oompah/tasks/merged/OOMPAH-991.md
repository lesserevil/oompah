---
id: OOMPAH-991
type: bug
status: Merged
priority: 1
title: Isolate WebSocket bootstrap tests from process-global state snapshots
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-10T10:30:40.633471Z'
updated_at: '2026-08-10T15:38:53.495022Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-749d3b5ec915
    project_id: proj-14849f1b
    task_id: OOMPAH-991
    target_state: Merged
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 918102097907d59840d1fc02f563c4428013d578966a16fd4bf2eb674faac141
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: 'PR #798 merged as 2ab880be5; exact OOMPAH-991 commit c4ad83e47 is contained
      in main and protected CI passed.'
    created_at: '2026-08-10T15:38:41.196063+00:00'
    selected_ref: origin/main
    selected_sha: 2ab880be5c25d7b5c70000845698d39d5d53d3c8
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-991
    target_state: Merged
    evidence_fingerprint: 918102097907d59840d1fc02f563c4428013d578966a16fd4bf2eb674faac141
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-10T15:38:51.508876+00:00'
  oompah.terminal_audit_result_intents: []
  version: 1
  pending_chain: []
  attempt_history: []
---
## Summary

Triggered by: OOMPAH-989

PR 798 exposed an order-dependent CI failure in test_ws_bootstrap_structure_preserved. OOMPAH-989 restart tests leave partial process-global server state snapshots, while the WebSocket _ws_isolation helper resets clients and orchestrator but not the snapshot/protocol cache, so xdist worker order controls the bootstrap payload. Scope: exactly save, clear, and restore all state cache authority/revision globals in the WebSocket helper and every restart regression that mutates them; add poison-cache and sentinel-restore regressions; preserve production partial-cache and fail-closed semantics. Run affected WebSocket, restart, and server tests with the deterministic leaking-test-then-victim order, repeated xdist stress, and the full Makefile gate. Acceptance: Python 3.11/3.12/3.13 CI is independent of worker assignment, cache globals are restored exactly, and no stale data or credentials are exposed.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-10 10:37
---
Test-isolation blocker fix is committed and pushed at exact head f2a3a397273c5d6f051ff6754b715bb4e64e2b8d on branch OOMPAH-989. Restart API tests now save and restore the complete server snapshot/protocol tuple under the snapshot then protocol locks. WebSocket isolation atomically clears that tuple to coherent unavailable defaults and restores the exact prior snapshot, timestamp, epoch, authority, signature, protocol epoch, state revision, and issue revision. Poison-cache and exact sentinel restoration regressions were added; production normalization was not changed. Evidence: original leaking-test then victim order passed 2/2 serial and 2/2 with xdist n=1; both new regressions passed 2/2; both affected files passed 44/44; all three known restart leakers followed by the victim passed 10/10 repeated xdist n=1 runs; compileall and git diff --check passed. No new full gate was run because this is the narrow PR 798 blocker requested for the already-gated OOMPAH-989 integration head. OOMPAH-991 remains In Progress for owner disposition.
---
author: oompah
created: 2026-08-10 10:46
---
Reviewer rejection of f2a3a397 is corrected and pushed at replacement exact head c4ad83e47b1492e7526098dcf5816b3dfd3eb50b. The isolation tuple is now strictly state-scoped: snapshot, timestamp, snapshot epoch, authority, signature, and state revision only. It neither saves nor restores protocol_epoch or issue_revision. WebSocket unavailable setup binds state_snapshot_epoch to the live protocol epoch while holding state_snapshot_lock then ws_protocol_lock, and leaves issue revision/snapshot/refresh ownership untouched. New controlled regressions prove a restart callback and a live WebSocket connection can advance issue invalidation while isolation is active, and state restoration does not rewind that issue generation or create a data_revision mismatch. Evidence at the replacement head: original leaker then victim passes serial 2/2 and xdist n=1 2/2; affected files pass 45/45; the 7-test pack covering all 3 known leakers, callback coherence, victim, poison cache, and WebSocket coherence passes 10/10 repeated xdist n=1 runs; compileall, diff check, secret hooks, and push all pass. No full gate was run per narrow blocker instruction.
---
author: oompah
created: 2026-08-10 10:57
---
Cross-version CI confirmation: PR #798 at exact head c4ad83e47b1492e7526098dcf5816b3dfd3eb50b passed the complete GitHub test matrix on Python 3.11, 3.12, and 3.13. This independently confirms the state-scoped WebSocket bootstrap isolation repair is no longer worker-order or interpreter-version dependent. The task remains In Progress until the shared integration PR lands.
---
author: oompah
created: 2026-08-10 15:38
---
Override by oompah-cli: terminal transition to Merged applied by project owner.

Reason: PR #798 merged as 2ab880be5; exact OOMPAH-991 commit c4ad83e47 is contained in main and protected CI passed.
---
<!-- COMMENTS:END -->
