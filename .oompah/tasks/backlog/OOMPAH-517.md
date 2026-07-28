---
id: OOMPAH-517
type: task
status: Backlog
priority: null
title: Reclaim quarantined cleanup trees with restrictive modes
parent: OOMPAH-502
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-28T16:44:23.886600Z'
updated_at: '2026-07-28T16:44:31.847773Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
