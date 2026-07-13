---
id: OOMPAH-200
type: task
status: Done
priority: 1
title: Replace the Release branches overlay with Release delivery UI
parent: OOMPAH-192
children: []
blocked_by:
- OOMPAH-196
- OOMPAH-198
- OOMPAH-199
labels: []
assignee: null
created_at: '2026-07-13T19:32:56.999746Z'
updated_at: '2026-07-13T22:51:55.535024Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
oompah.agent_run_id: 5fa5f4e4-6a61-409e-bedf-1b2548419b53
---
## Summary

Plan reference: plans/release-delivery-commit-inventory.md sections 2 and 6.

Replace the dashboard Release branches toolbar action and _rbi overlay with the project-scoped Release delivery overlay. Implement project selection, source metadata, release-line filters/columns, search, needs-delivery/all filter, pagination, accessible commit selection, multi-target confirmation, queue outcome feedback, and a per-row evidence drawer. Retain task/epic detail release controls but point them at ledger-backed data.

Acceptance criteria
- The toolbar opens Release delivery, defaults to the dashboard project filter, and never mixes projects.
- Each row renders a safe selectable source commit and text-labeled per-branch status; merge commits are informational and not selectable.
- Selecting commits and targets calls the new API, displays per-pair outcomes, clears only successful/skipped selection, and reloads page one.
- Delivered-by-cherry-pick and delivered-by-ancestry clearly show different evidence.
- Legacy Release branches overlay/state/helpers are removed; task/epic release controls still work.

Tests
- Add browser/template tests for project defaulting, filters, search, pagination, status rendering, selection/confirmation, outcome feedback, empty/error states, special-character escaping, keyboard Escape, and focus restoration.
- Add regression coverage that no untrusted API text is interpolated into inline event handlers.

Dependencies
- OOMPAH-196, OOMPAH-198, and OOMPAH-199.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-13 22:35
---
Agent dispatched (profile: default)
---
author: oompah
created: 2026-07-13 22:35
---
Focus: Duplicate Investigator
---
author: oompah
created: 2026-07-13 22:35
---
Understanding: As the Duplicate Investigator, I need to determine whether OOMPAH-200 ('Replace the Release branches overlay with Release delivery UI') is a duplicate of any existing issue before proceeding with implementation. I will search for similar tasks covering: release delivery UI, release branches overlay replacement, commit inventory, and related topics. Plan reference is plans/release-delivery-commit-inventory.md sections 2 and 6. Will report findings shortly.
---
author: oompah
created: 2026-07-13 22:36
---
Duplicate investigation complete: OOMPAH-200 is unique. The sibling tasks in the OOMPAH-192 epic cover: ledger schema (193), migration (194), queue/executor refactoring (195), task/epic compat (196), CommitInventoryService (197), GET inventory API (198), POST queue API (199), docs/deprecation (201), and e2e (202). No archived, done, or open task replaces the dashboard Release branches overlay/_rbi with a UI. All blockers (OOMPAH-196, OOMPAH-198, OOMPAH-199) are Done. Proceeding with implementation: replacing the _rbi overlay and toolbar action with the Release delivery overlay (sections 2 and 6 of plans/release-delivery-commit-inventory.md).
---
author: oompah
created: 2026-07-13 22:41
---
Discovery: Confirmed the scope. The dashboard.html has: (1) RBI CSS at ~lines 970-1139 (release-branch-inspector-overlay, rbi-* classes), (2) toolbar button at line 2102 (btn-release-branches / openReleaseBranchInspector), (3) RBI JS at lines 6695-6920 (_rbiCurrentProjectId, _rbiLoadBranchList, etc.), (4) RBI HTML overlay at lines 7145-7164. All four must be replaced with the new Release delivery overlay. Dependencies (OOMPAH-196, OOMPAH-198, OOMPAH-199) are all Done. The GET API at /api/v1/projects/{id}/release-delivery/commits returns rows with sha/selectable/release_status cells (state: not_selected|open|in_progress|in_review|blocked|delivered|archived, evidence: delivery|ancestry|null). The POST API returns created/already_active/already_delivered/invalid per-pair outcomes. Beginning implementation now.
---
author: oompah
created: 2026-07-13 22:50
---
Implementation complete. Changes to oompah/templates/dashboard.html:

1. CSS: Removed all RBI CSS (~170 lines), added RDI CSS (~290 lines) with overlay, panel, table, filter controls, status cell variants (not_selected/open/in_progress/in_review/blocked/delivered/archived), delivered-ancestry distinct from delivered-delivery, clickable cells, action bar, pagination, drawer, outcome banner.

2. Toolbar: Changed 'Release branches' button (openReleaseBranchInspector) to 'Release delivery' button (openReleaseDelivery).

3. JS: Removed 220-line RBI JS (_rbiCurrentProjectId/Branch/Loading, loadBranchList, loadBranchAddendums, etc). Added 860-line RDI JS with: state object (_rdiProjectId, _rdiVisibleBranches, _rdiFilter, _rdiQuery, _rdiCursor, _rdiSourceHead, _rdiSelectedSHAs, _rdiGen, _rdiCurrentPageData, _rdiOpener, _rdiDrawerSHA); open/close with focus restoration; Escape handler (closes drawer first, then overlay); project defaulting from dashboard filter; _rdiLoadPage with generation counter (ignores stale responses), 409/source_changed handling, filter/query/branches/cursor params; DOM-only rendering (_rdiRenderRow/_rdiRenderCell use createElement/textContent, never innerHTML for API text); all 7 status labels; delivered-ancestry vs delivered-cherry-pick distinction; selection with indeterminate checkbox; _rdiQueueSelected (POST with Idempotency-Key, ordered SHAs, clear only success/skipped, keep invalid selected); outcome banner; evidence drawer (SHA, parents, subject, author, association, per-branch evidence with distinct cherry-pick vs ancestry labels, PR links, delivery IDs, result SHAs); filter/search/branch filter handlers.

4. HTML: Removed RBI overlay HTML, added RDI overlay + evidence drawer HTML with proper roles, aria attributes, focus management.

5. Retained: openAddReleaseBranchesDialog, renderReleaseAddendumsSection, renderEpicReleaseAddendumsSection, add-release-branches-dialog HTML (task/epic release controls unchanged).

Tests: Added tests/test_dashboard_release_delivery_ui.py with 249 tests covering CSS, HTML, state, functions, open/close, project defaulting, data loading, status rendering, XSS prevention, selection, queue delivery, outcome feedback, evidence drawer, filter/search, empty/error states, pagination, retained controls, accessibility, legacy removal.
---
author: oompah
created: 2026-07-13 22:51
---
Verification: All 8782 tests pass (249 new in test_dashboard_release_delivery_ui.py, 28 skipped, 0 failures). Branch epic-OOMPAH-192 pushed and up to date with origin.
---
author: oompah
created: 2026-07-13 22:51
---
Completion: Delivered the Release delivery overlay (plans/release-delivery-commit-inventory.md sections 2 and 6).

Summary of changes:
- dashboard.html: Removed _rbi overlay (CSS/JS/HTML), added _rdi overlay (CSS/JS/HTML)
- tests/test_dashboard_release_delivery_ui.py: 249 new tests

Acceptance criteria satisfied:
✓ Toolbar opens Release delivery, defaults to dashboard project filter
✓ Each row renders safe selectable source commit and text-labeled per-branch status; merge commits are informational and not selectable
✓ Selecting commits and targets calls new API, displays per-pair outcomes, clears only successful/skipped selection, reloads page one
✓ Delivered-by-cherry-pick and delivered-by-ancestry clearly show different evidence (distinct labels AND distinct CSS classes)
✓ Legacy Release branches overlay/state/helpers removed; task/epic release controls (openAddReleaseBranchesDialog, renderReleaseAddendumsSection, etc.) still work

Tests cover: CSS, HTML, state, functions, open/close, Escape, focus restoration, project defaulting, filters, search, pagination, status rendering, selection/confirmation, outcome feedback, empty/error states, special-character escaping (textContent/DOM, never innerHTML for API text), XSS prevention, drawer evidence, and accessibility attributes.
---
<!-- COMMENTS:END -->
