---
id: OOMPAH-517
type: task
status: In Validation
priority: null
title: Reclaim quarantined cleanup trees with restrictive modes
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T16:44:23.886600Z'
updated_at: '2026-08-04T20:21:14.314213Z'
work_branch: epic-OOMPAH-502
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.work_branch: epic-OOMPAH-502
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-0e35765539f9
    project_id: proj-14849f1b
    task_id: OOMPAH-517
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f4ec0a7adbe13e9aa4e70decd071744f03811faf6a845f4ea1603f2b2fb34a31
    attempts:
    - version: 1
      attempt_id: attempt-d9bb7f07c5ba
      target_state: Archived
      request_state: in_progress
      evidence_fingerprint:
        version: 1
        algorithm: sha256
        digest: f4ec0a7adbe13e9aa4e70decd071744f03811faf6a845f4ea1603f2b2fb34a31
      created_at: '2026-08-04T20:21:12.727934+00:00'
      provider_id: prov-651d553c
      model: opus
      started_at: '2026-08-04T20:21:12.727934+00:00'
      branch_key: epic-OOMPAH-502
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-04T18:29:10.392593+00:00'
    updated_at: '2026-08-04T20:21:12.727934+00:00'
  attempt_history:
  - version: 1
    attempt_id: attempt-d9bb7f07c5ba
    target_state: Archived
    request_state: in_progress
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: f4ec0a7adbe13e9aa4e70decd071744f03811faf6a845f4ea1603f2b2fb34a31
    created_at: '2026-08-04T20:21:12.727934+00:00'
    provider_id: prov-651d553c
    model: opus
    started_at: '2026-08-04T20:21:12.727934+00:00'
    branch_key: epic-OOMPAH-502
---
## Summary

Implementation scope\n\nHarden oompah/storage_cleanup.py so a stale Oompah-owned temp tree remains removable when test artifacts or caches contain owner read-only directories/files. The live pressure scan currently quarantines these entries successfully but shutil.rmtree then fails with PermissionError on nested mode-0555 release directories, causing repeated errors and stranded .oompah-cleanup-* trees. Keep the ownership boundary and symlink protections: only normalize owner permission bits after the direct child has been atomically moved to a quarantine name inside the configured owned temp root; never follow symlinks; do not use privilege escalation; preserve the existing batch and byte limits.\n\nTests\n\nAdd a regression in tests/test_storage_cleanup.py that creates a stale nested tree with restrictive directory/file modes, proves cleanup removes it, and verifies an external symlink target is untouched. Retain the existing injected permission-error observability test for genuinely unrecoverable failures. Run the focused storage cleanup tests and the project test gate.\n\nAcceptance criteria\n\nA user-owned stale tree containing owner read-only directories is reclaimed without an error; quarantine leftovers from recoverable mode restrictions do not accumulate; symlinks are never followed; genuinely unrecoverable errors remain visible in maintenance status; and all relevant tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 16:44
---
Claimed for this session as part of OOMPAH-502. I will implement and validate it manually on the shared epic branch; leave it undispatched while I work.
---
author: oompah
created: 2026-07-28 16:45
---
Implemented on epic-OOMPAH-502 at a2414d5ba. Cleanup now grants owner rwx only to real directories after atomic quarantine inside the owned root, then removes the tree without following symlinks. Regression covers nested 0555 directories, a 0400 file, and an external symlink target. Focused result: 10 passed in 0.83s; full branch gate remains assigned to OOMPAH-510 after prerequisite integration.
---
author: oompah
created: 2026-07-28 16:45
---
Reclaimed restrictive-mode stale trees safely after quarantine; 10 focused storage cleanup tests pass.
---
author: oompah
created: 2026-08-04 18:29
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
