---
id: OOMPAH-173
type: task
status: In Progress
priority: 1
title: Add release-addendum schema and metadata repository
parent: OOMPAH-172
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-13T02:35:38.417683Z'
updated_at: '2026-07-13T02:57:46.623756Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 4f3d1a09-525d-4cec-9991-4743bacdf423
---
## Summary

Read sections 4 and 4.2 of plans/release-branch-addendums.md. Create oompah.release_addendum_schema with a typed ReleaseAddendum model, status enum (open, in_progress, in_review, blocked, merged, archived), parser/serializer, deterministic ID/work-branch helpers, and transition validation. Add a metadata repository/helper that reads and atomically replaces only oompah.release_addendums on a source task. Enforce one active addendum per target branch, immutable nonempty ordered commit snapshots, and no client-controlled execution evidence. Tests: valid round trips; malformed records; duplicate targets; illegal transitions; deterministic escaping/sanitization; and writes preserving unrelated metadata. Acceptance: no production caller is changed yet, but the module has complete unit coverage and is usable without release-pick child metadata.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 02:54
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 02:54
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 02:57
---
Understanding: Investigated for duplicate — OOMPAH-173 is a unique child of the OOMPAH-172 epic (no overlap with OOMPAH-174 through OOMPAH-184). This is a first-slice foundation task.

Plan: Implement oompah/release_addendum_schema.py with AddendumStatus enum (open/in_progress/in_review/blocked/merged/archived), ReleaseAddendum dataclass with all fields from section 4, VALID_TRANSITIONS from section 4.2, is_valid_transition(), make_addendum_id/work_branch/worktree_key deterministic helpers, parse_addendums/addendums_to_raw serializer, and an AddendumRepository that reads/writes only oompah.release_addendums on a source task atomically via TrackerProtocol.set_metadata_field, enforcing one active addendum per target branch and immutable non-empty commits. Followed by full unit test coverage in tests/test_release_addendum_schema.py.
---
<!-- COMMENTS:END -->
