---
id: OOMPAH-910
type: bug
status: Done
priority: 1
title: Prevent owner-revision cross-thread project-lock deadlock
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T13:34:11.755473Z'
updated_at: '2026-08-09T21:42:47.300488Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-ef16e170ed76
    project_id: proj-14849f1b
    task_id: OOMPAH-910
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: a74d276a32b8e492fc90002cc8cf393422aef29a1f577d1159d83f708c80d657
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:28:03.727574+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-910
    target_state: Done
    evidence_fingerprint: a74d276a32b8e492fc90002cc8cf393422aef29a1f577d1159d83f708c80d657
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:28:11.786974+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Owner-reviewed terminal implementation is retained. The Done child is
      durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
      exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
    marked_at: '2026-08-09T21:42:45.669842+00:00'
    updated_at: '2026-08-09T21:42:45.669842+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Owner-reviewed terminal implementation is retained. The Done child is
        durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
        exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
      recorded_at: '2026-08-09T21:42:45.669842+00:00'
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

Fix the terminal-provenance new-revision endpoint deadlock where ProvenanceGuardedTracker.authorize_owner_revision holds ProjectStore.project_write_lock while TaskTransitionService offloads the tracker update to another thread that attempts to acquire the same thread-owned RLock. Implement a fail-closed lock protocol: validate suppression/status under the project lock, release it for the journaled transition, then reacquire and revalidate Open plus the unchanged suppression generation before clearing the marker. Cover the exact retain -> interrupted metadata clear -> retry API sequence and a bounded cross-thread project-lock regression in tests/test_provenance_suppression.py and tests/test_provenance_suppression_api.py. Acceptance: focused provenance suites complete without hanging, preserve Open+suppressed retry safety, and the full branch gate passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 13:35
---
Directly claimed. Root cause reproduced as a deterministic cross-thread RLock deadlock in the exact API test. Implemented a fail-closed two-phase project-lock protocol: suppression/status validation under lock, journaled Open transition without the outer RLock, then locked Open+generation revalidation before suppression clearance. Focused provenance suites pass 36/36; exact full gate remains pending after unrelated fixture failures are repaired.
---
author: oompah
created: 2026-08-08 16:28
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope is contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
