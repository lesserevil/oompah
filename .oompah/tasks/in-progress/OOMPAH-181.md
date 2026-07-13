---
id: OOMPAH-181
type: task
status: In Progress
priority: 2
title: Build epic release-addendum approval and snapshot UI
parent: OOMPAH-172
children: []
blocked_by:
- OOMPAH-176
labels: []
assignee: null
created_at: '2026-07-13T02:36:15.200697Z'
updated_at: '2026-07-13T05:39:38.054071Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: ada2ad3b-35e9-489e-b75d-8d74765e509f
---
## Summary

Read section 7 Epic detail of plans/release-branch-addendums.md. Add epic-specific release-addendum UI using the same supported-branch selection behavior as tasks. The API response and UI must show one addendum per selected target branch, snapshot size, included merged descendant count, status, PR link, and an expandable immutable child/commit snapshot. Do not reuse the old child-by-branch release-pick matrix or apply-all behavior. Tests: API rendering contract, merged-descendant snapshot display, no automatic inclusion of descendants merged after approval, and accessible dialog interactions. Acceptance: an operator can understand exactly which already-merged descendants an epic addendum will deliver without creating per-child backport tasks.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 05:38
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 05:38
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 05:39
---
Understanding: OOMPAH-181 is NOT a duplicate. Searched all tasks under OOMPAH-172 epic. OOMPAH-180 (task detail UI, in-progress) and OOMPAH-182 (branch inspection) cover different subsections. OOMPAH-181 uniquely covers the epic detail UI for release addendums (section 7 Epic detail of plans/release-branch-addendums.md).

Scope: Replace the child-by-branch release-pick matrix in epic detail with an epic addendum list (one row per target branch) showing: target branch, snapshot size, included-child count, status, PR link. Add expandable immutable child/commit snapshot. Use same dialog as tasks (branch catalog, checkboxes, idempotency key). Apply-all behavior must be removed. OOMPAH-176 (approval API) is Done.

Plan: (1) Read OOMPAH-180's implementation for dialog/catalog patterns; (2) Find epic-specific code in dashboard.html; (3) Add renderEpicReleaseAddendumsSection() with expandable snapshot; (4) Reuse/adapt Add release branches dialog for epics; (5) Add required tests.
---
<!-- COMMENTS:END -->
