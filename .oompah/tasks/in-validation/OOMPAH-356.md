---
id: OOMPAH-356
type: epic
status: In Validation
priority: 1
title: Reduce unfinished epic branch synchronization churn
parent: null
children:
- OOMPAH-357
- OOMPAH-358
- OOMPAH-359
blocked_by: []
labels:
- reliability
- workflow
assignee: null
created_at: '2026-07-22T01:23:32.887223Z'
updated_at: '2026-08-02T01:30:43.922063Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-609917f758c9
    project_id: proj-14849f1b
    task_id: OOMPAH-356
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: afe4a724470fb72d93d5fc3e6ef18e8d543f1b54864f887b84c39a678efa8e3f
    attempts:
    - version: 1
      attempt_id: attempt-50c3d6991111
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: afe4a724470fb72d93d5fc3e6ef18e8d543f1b54864f887b84c39a678efa8e3f
      created_at: '2026-08-02T01:30:43.014536+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:30:43.014536+00:00'
      branch_key: OOMPAH-356
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:44.770084+00:00'
    updated_at: '2026-08-02T01:30:43.014536+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-50c3d6991111
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: afe4a724470fb72d93d5fc3e6ef18e8d543f1b54864f887b84c39a678efa8e3f
    created_at: '2026-08-02T01:30:43.014536+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:30:43.014536+00:00'
    branch_key: OOMPAH-356
---
## Summary

Change Oompah's branch-maintenance policy so incomplete epic branches do not receive routine merges or rebases from main, and never synchronize directly with other epic branches. Integration must occur through main. Rebase work is permitted only for an actionable condition: preparing or refreshing an epic PR, a merge-blocking conflict, an explicit user request, or a configured long-lived/stale branch threshold. Default behavior must detect and surface staleness without changing the branch.\n\nAcceptance criteria:\n- No automatic main-to-epic merge/rebase occurs merely because main advanced.\n- No epic-to-epic merge/rebase is scheduled.\n- The UI/API exposes detected branch staleness and the actionable reason for any scheduled rebase.\n- Existing projects migrate to the conservative default without configuration changes.\n- Child tasks implement policy, scheduling, and test coverage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:30
---
Completed, tested, pushed, and restarted the conservative epic synchronization policy.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: the conservative unfinished-epic synchronization policy is present on origin/main in commit 2ba37886b. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 2ba37886b and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
