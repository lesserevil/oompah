---
id: OOMPAH-626
type: bug
status: In Validation
priority: 1
title: Supersede in-flight terminal audits when evidence changes
parent: OOMPAH-585
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-07-30T22:02:35.998442Z'
updated_at: '2026-07-30T22:11:27.898321Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.integration:
  version: 1
  state: integrated
  attempts: 1
  task_branch: epic-OOMPAH-585--task-OOMPAH-626
  base_branch: epic-OOMPAH-585
  base_sha: 078bcd40c159a7906c30444ceae2e563b48e1ca3
  head_sha: 5c45358226b238c1c9c2bdeee8bf9c85489d6f19
  integrated_sha: 5c45358226b238c1c9c2bdeee8bf9c85489d6f19
  submitted_at: '2026-07-30T22:06:05.301194+00:00'
  updated_at: '2026-07-30T22:11:18.407047+00:00'
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-f30cc257120d
    project_id: proj-14849f1b
    task_id: OOMPAH-626
    target_state: Done
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: bb45021285ea3083ae52600f71d87eeb03507a993e90fb38e27235ce2a4af9ee
    attempts: []
    requested_by:
      version: 1
      identity: oompah-integration
      source: service
    previous_state: Ready to Integrate
    created_at: '2026-07-30T22:11:25.573500+00:00'
  attempt_history: []
---
## Summary

Implementation scope: update TerminalTransitionCoordinator transition staging so a new request for the same target with a changed evidence fingerprint supersedes an existing in-progress audit record as well as pending and completed records. The old worker may finish, but its result must fail the existing audit-id/state/fingerprint CAS and must never apply a terminal state to stale evidence. Preserve coalescing for identical evidence and the ordered Done/Merged/Archived chain contract. Relevant context: OOMPAH-591 gained audit-0e821c979fd2 while audit-85eb5879d029 was still in progress; recovery later changed the old record back to pending, leaving two eligible Done audits with different fingerprints. Tests: reproduce staging changed evidence over an in-progress record, verify only the fresh record remains eligible, verify a late result for the superseded record is rejected, and run focused coordinator/dispatcher tests plus the Makefile gate. Acceptance criteria: one active audit per target/evidence revision; stale in-flight results cannot close the task; focused and complete tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-30 22:03
---
Fixed the changed-evidence race: transition staging now supersedes matching in-progress records, leaving only the fresh revision eligible. The existing result CAS rejects a late verdict from the superseded worker. Verification: 144 focused transition/auditor/override tests passed; terminal mutation scan passed.
---
author: oompah
created: 2026-07-30 22:03
---
Supersede in-progress audits on changed evidence and reject stale late verdicts through the existing CAS.
---
author: oompah
created: 2026-07-30 22:06
---
Extended the fix to the exact persisted OOMPAH-591 shape: identical in-progress requests now coalesce instead of duplicating, and coalescing a fresh record repairs older active records with stale fingerprints by superseding them. Verification now covers 152 transition/dispatch/override/archive tests plus the terminal mutation scan.
---
author: oompah
created: 2026-07-30 22:06
---
Supersede changed in-flight evidence, coalesce identical in-progress requests, and self-heal stale duplicate revisions.
---
author: oompah
created: 2026-07-30 22:11
---
Queued for terminal transition to Done. An auditor will review and apply the terminal status.
---
<!-- COMMENTS:END -->
