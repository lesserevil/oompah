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
updated_at: '2026-07-13T06:01:16.876432Z'
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
author: oompah
created: 2026-07-13 05:52
---
Discovery: OOMPAH-181 is NOT a duplicate. Key findings:

1. OOMPAH-180 (Task detail UI, In Progress) already added renderReleaseAddendumsSection() and the Add release branches dialog in dashboard.html.
2. The GET /api/v1/issues/{id}/release-addendums endpoint exists (OOMPAH-180).
3. The POST approval endpoint exists (OOMPAH-176, Done).
4. The ReleaseAddendum schema does NOT yet have included_child_ids field.
5. The approval endpoint does NOT differentiate between tasks and epics (uses same commit resolution for both).
6. renderReleaseAddendumsSection() is called for ALL issues including epics, but doesn't show snapshot_size, included_child_count, or expandable child/commit snapshot.
7. Old epic release-pick matrix endpoints still exist (GET matrix, POST apply-all) but dashboard already calls renderReleaseAddendumsSection instead.

Implementation plan:
1. Add included_child_ids field to ReleaseAddendum schema
2. Add resolve_epic_addendum_commits() in release_addendum_approval.py
3. Update approve_release_addendums() to accept+store included_child_ids
4. Update server.py POST endpoint to detect epics and use epic-specific commit resolution
5. Add renderEpicReleaseAddendumsSection() in dashboard.html (with snapshot_size, included_child_count, expandable snapshot)
6. Update openDetailPanel() to dispatch to epic renderer for epics
7. Add tests: schema included_child_ids, API rendering contract, no-auto-inclusion, accessible dialog
---
author: oompah
created: 2026-07-13 06:00
---
Implementation: All changes complete.

1. oompah/release_addendum_schema.py: Added included_child_ids: list[str] field to ReleaseAddendum. Updated from_raw() (optional, defaults to []), to_raw() (always serialized), and transition() (preserved across lifecycle changes).

2. oompah/release_addendum_approval.py: Added resolve_epic_addendum_commits() that collects commits from all Merged descendants in order, deduplicates SHAs, returns (commits, included_child_ids). Uses tracker.fetch_children() + MERGED status filter. Raises CommitResolutionError when no Merged descendants found. Also updated approve_release_addendums() to accept included_child_ids parameter.

3. oompah/server.py: POST /release-addendums now detects issue_type=epic and calls resolve_epic_addendum_commits instead of resolve_addendum_commits. Passes included_child_ids to approve_release_addendums().

4. oompah/templates/dashboard.html: Added CSS for epic addendum UI (8 new CSS classes). Added renderEpicReleaseAddendumsSection() showing: target branch, snapshot size (commit count badge), included-child count badge, status, PR link, and expandable immutable snapshot (child list + commit list with aria-expanded). Updated openDetailPanel() to dispatch to renderEpicReleaseAddendumsSection for epics, renderReleaseAddendumsSection for tasks.

5. tests/test_epic_release_addendum_ui.py: 50 new tests covering schema parsing/serialization/transitions, API rendering contract, no-auto-inclusion invariant, epic commit resolution, POST endpoint epic detection, UI rendering contract, dispatch logic, and CSS classes.

No old child-by-branch matrix or apply-all behavior referenced.
---
author: oompah
created: 2026-07-13 06:01
---
Verification: make test — 7886 passed, 28 skipped, 12 warnings (0 failures). 50 new tests all pass.

Test coverage:
- 8 schema tests: included_child_ids parsing/serialization/round-trip/transition preservation
- 3 API contract tests: GET response includes included_child_ids for epics (and empty for tasks)
- 7 epic commit resolution unit tests: merged-child collection, non-merged exclusion, SHA deduplication, error cases, no-auto-inclusion invariant
- 4 POST endpoint integration tests: epic detection, response includes child_ids, 409 for no merged children, task path does not use epic resolution
- 15 UI rendering tests: function defined, branch/status/PR/snapshot-size/child-count/toggle/aria, empty state, gated button, no task_id link
- 3 dispatch tests: epic → epic renderer, task → task renderer, issue_type check
- 8 CSS class tests: all new epic addendum CSS classes present

All acceptance criteria met: operator can see exactly which already-merged descendants an epic addendum will deliver (via child ID list) without creating per-child backport tasks.
---
<!-- COMMENTS:END -->
