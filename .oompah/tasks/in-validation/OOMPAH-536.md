---
id: OOMPAH-536
type: bug
status: In Validation
priority: 1
title: Route implementation away from completed duplicate preflight focus
parent: null
children: []
blocked_by: []
labels:
- needs:backend
- needs:test
assignee: null
created_at: '2026-07-28T23:51:54.516163Z'
updated_at: '2026-08-05T00:41:31.004773Z'
work_branch: OOMPAH-536
target_branch: main
review_url: https://github.com/lesserevil/oompah/pull/570
review_number: '570'
merged_at: null
oompah.review_url: https://github.com/lesserevil/oompah/pull/570
oompah.review_number: '570'
oompah.work_branch: OOMPAH-536
oompah.target_branch: main
oompah.terminal_audit:
  queued_comment_posted: true
  version: 1
  pending_chain:
  - version: 1
    audit_id: audit-41803391d996
    project_id: proj-14849f1b
    task_id: OOMPAH-536
    target_state: Archived
    request_state: pending
    evidence_fingerprint:
      version: 1
      algorithm: sha256
      digest: ecaee7ad6c6c3a07543aba0466f343c7dc9329c8f8ac97c2b9a1edcaa6dd42b8
    attempts: []
    requested_by:
      version: 1
      identity: oompah
      source: auto_archive
    previous_state: Merged
    created_at: '2026-08-05T00:41:21.197322+00:00'
  attempt_history: []
---
## Summary

Production follow-up to OOMPAH-535 / PR #569.

Incident: the corrected read-only preflight for OOMPAH-469 completed and its structured no_duplicate record became implementation-eligible, but ordinary focus selection chose duplicate_detector again because the new server-owned structured result no longer depends on the legacy focus-complete:duplicate_detector label. The implementation worker therefore started under the wrong prompt. It was stopped before modifying the clean shared epic worktree, and the oompah project is paused.

Implementation scope:
- Treat a current, conclusive no_duplicate DuplicateScreeningRecord as completion of the duplicate_detector focus during both deterministic and async ordinary focus selection.
- Preserve legacy focus-complete labels, revision-aware invalidation, forced preflight selection, and all other focus handoffs. Do not require the read-only screening agent to mutate tracker labels/comments.

Required tests:
- A current checked no_duplicate record excludes duplicate_detector from ordinary deterministic and async selection.
- Editing duplicate-relevant task content makes the record stale and permits a new forced preflight rather than permanently suppressing screening.
- The post-preflight implementation route selects a non-duplicate implementation focus.
- Run focused tests and make test.

Acceptance criteria:
After a successful preflight, implementation cannot run with duplicate_detector; OOMPAH-469 advances under the auditor/appropriate implementation focus; no task/worktree mutation is required from the screening worker; and production dispatch resumes without a repeat loop.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-28 23:52
---
Claimed directly during production verification of OOMPAH-535. The misfocused OOMPAH-469 run was stopped before any worktree change; the oompah project remains paused while this follow-up is implemented and tested.
---
author: oompah
created: 2026-08-05 00:41
---
Queued Archived audit: Aged Merged auto-archive (closed 7 days ago). An auditor will review before the task is retired.
---
<!-- COMMENTS:END -->
