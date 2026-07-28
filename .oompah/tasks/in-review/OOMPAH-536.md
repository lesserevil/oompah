---
id: OOMPAH-536
type: bug
status: In Review
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
updated_at: '2026-07-28T23:55:39.511820Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
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
<!-- COMMENTS:END -->
