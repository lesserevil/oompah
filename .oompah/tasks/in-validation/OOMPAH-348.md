---
id: OOMPAH-348
type: epic
status: In Validation
priority: 1
title: Eliminate Oompah service wedge failure modes
parent: null
children:
- OOMPAH-349
- OOMPAH-350
- OOMPAH-351
- OOMPAH-352
blocked_by: []
labels:
- reliability
- service-wedge
assignee: null
created_at: '2026-07-22T00:56:17.834972Z'
updated_at: '2026-08-02T01:26:25.365516Z'
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
    audit_id: audit-2977f93aea96
    project_id: proj-14849f1b
    task_id: OOMPAH-348
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 019e7f713efd2c0524db538b89e053c4f37dea2387e5a8c6a0bdcc82b735c98f
    attempts:
    - version: 1
      attempt_id: attempt-ca7274bb7555
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: 019e7f713efd2c0524db538b89e053c4f37dea2387e5a8c6a0bdcc82b735c98f
      created_at: '2026-08-02T01:26:16.227144+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-02T01:26:16.227144+00:00'
      branch_key: OOMPAH-348
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-02T01:12:18.712838+00:00'
    updated_at: '2026-08-02T01:26:16.227144+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-ca7274bb7555
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: 019e7f713efd2c0524db538b89e053c4f37dea2387e5a8c6a0bdcc82b735c98f
    created_at: '2026-08-02T01:26:16.227144+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-02T01:26:16.227144+00:00'
    branch_key: OOMPAH-348
---
## Summary

Implement and verify the durable reliability fixes identified from production wedge incidents: enforce real tracker timeouts, separate scheduler work from HTTP serving, bound shutdown, and capture diagnostics for any future stall. Child tasks define the independently testable implementation units. Success means a slow or hung tracker/git operation cannot make the UI/API unresponsive or prevent a restart.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:16
---
Completed and pushed the durable scheduler wedge fixes; Exocomp state branch migration is complete.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: the aggregate scheduler wedge fixes is present on origin/main in commit 6dd2cdfcf. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
author: oompah
created: 2026-07-26 00:27
---
Verified delivered on origin/main in 6dd2cdfcf and reconciled stale Done state.
---
author: oompah
created: 2026-08-02 01:12
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
author: oompah
created: 2026-08-02 01:26
---
Auditor dispatched (attempt #1, candidate: prov-651d553c/opus)
---
<!-- COMMENTS:END -->
