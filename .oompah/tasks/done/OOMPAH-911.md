---
id: OOMPAH-911
type: bug
status: Done
priority: 1
title: Repair durable-transition regressions exposed by exact full gate
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T13:38:22.228736Z'
updated_at: '2026-08-09T21:42:50.456374Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
oompah.terminal_audit:
  oompah.terminal_override_records:
  - version: 1
    override_id: override-146ff0f468fb
    project_id: proj-14849f1b
    task_id: OOMPAH-911
    target_state: Done
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 1cc41a2ce4aeb1ac2d7878f54690e2ff3e9dc08757d4f62989c6b1a870b621ea
    authorized_by:
      version: 1
      identity: oompah-cli
      source: api
    reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d;
      exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b).
      This task scope is contained in that validated head; owner override avoids fabricating
      a separate branch/integration generation.
    created_at: '2026-08-08T16:28:36.962320+00:00'
    applied: true
  oompah.terminal_audit_retirements:
  - project_id: proj-14849f1b
    task_id: OOMPAH-911
    target_state: Done
    evidence_fingerprint: 1cc41a2ce4aeb1ac2d7878f54690e2ff3e9dc08757d4f62989c6b1a870b621ea
    audit_ids: []
    kind: override
    applied: true
    retired_at: '2026-08-08T16:28:44.543982+00:00'
  oompah.terminal_audit_result_intents: []
  oompah.terminal_provenance_suppression:
    version: 1
    suppressed: true
    authority_generation: 0
    reason: Owner-reviewed terminal implementation is retained. The Done child is
      durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
      exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
    marked_at: '2026-08-09T21:42:48.898852+00:00'
    updated_at: '2026-08-09T21:42:48.898852+00:00'
    history:
    - kind: mark
      actor:
        version: 1
        identity: oompah-cli
        source: api
      reason: Owner-reviewed terminal implementation is retained. The Done child is
        durably composed into epic OOMPAH-763; its current parent_rollup_review head_required
        exhaustion is the OOMPAH-975 null-head transition bug. Do not rearm implementation.
      recorded_at: '2026-08-09T21:42:48.898852+00:00'
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

Repair the exact-gate failures exposed after OOMPAH-909 made resource cleanup deterministic. Preserve StateBranchFetchError warning/503 classification after TaskTransitionService wraps tracker failures in redacted TaskTransitionNotApplied outcomes (oompah/server.py; tests/test_state_branch_fetch_error.py). Fix revoked-submission recovery so normalized project scope is retained and interrupted recovery publication fences Open against the currently accepted head rather than the distinct unaccepted recovery snapshot (oompah/orchestrator.py; tests/test_submission_fencing.py). Update centralized-transition test doubles to mutate authoritative point-read state and recognize already-applied Ready states without redundant writes. Repair the integration-queue cancellation proxy so deterministic teardown closes the real SQLite connection. Acceptance: focused state-branch, submission-fencing, and integration-queue regressions pass; no resource cleanup error remains; terminal audit/secret scans and the exact full four-worker branch gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 13:38
---
Implementation and focused validation are already in progress on the composed systemic branch; direct owner claim follows.
---
author: oompah
created: 2026-08-08 16:28
---
Override by oompah-cli: terminal transition to Done applied by project owner.

Reason: Systemic composition delivered and deployed at d796a4be9a7b0f2dd079cef8ce17e6ec6ecfd62d; exact-head make test passed (18,744 passed, 7 skipped, 2 xfailed; artifact /home/shedwards/.oompah/tmp/OOMPAH-763-full-d796a4b.R3hV9b). This task scope is contained in that validated head; owner override avoids fabricating a separate branch/integration generation.
---
<!-- COMMENTS:END -->
