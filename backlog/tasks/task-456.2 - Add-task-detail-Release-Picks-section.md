---
id: TASK-456.2
title: Add task detail Release Picks section
status: Done
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 22:33'
labels:
  - task
dependencies:
  - TASK-456.1
parent_task_id: TASK-456
priority: high
ordinal: 104000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Render a compact Release Picks section in the task detail panel showing target branch, status, child task, PR link, and next action. Include an Add Release Picks action.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 21:23
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 21:23
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 22:14
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 22:15
---
Understanding: TASK-456.2 is NOT a duplicate. Searched 'Release Picks', 'task detail release', 'backport UI'. TASK-456.4 covers epic-level matrix, TASK-456.3 covers the Add Release Picks modal, TASK-456.5 covers validation state display. This task is distinct: it renders the compact Release Picks section IN the task detail panel (list of per-branch entries with target branch, status, child task, PR link, next action) and an 'Add Release Picks' action button. TASK-456.1 (Done) provides the backend API this will consume. Plan: explore the frontend/UI code, find the task detail panel component, implement the Release Picks section using the API from TASK-456.1, add tests.
---

author: oompah
created: 2026-06-08 22:21
---
Discovery: Task detail panel is in oompah/templates/dashboard.html, built with vanilla JS string interpolation in openDetailPanel() (line 3375). The API for release picks was completed in TASK-456.1 at GET /api/v1/issues/{id}/release-picks returning {identifier, backports: [{branch, status, task_id, pr_url, pr_id, is_valid, validation_error}], backport_of: {source, status}|null}. Plan: (1) add CSS for .release-picks-list, .release-pick-entry, .release-pick-status etc, (2) add JS helpers renderReleasePicksSection() and releasePickNextAction(), (3) modify openDetailPanel() to fetch release picks in parallel and render the section before the Comments block, (4) add placeholder openAddReleasePicksModal() that fires a custom event, (5) add tests in test_dashboard_release_picks_section.py using the existing HTML-introspection pattern.
---

author: oompah
created: 2026-06-08 22:31
---
Implementation: Added Release Picks section to dashboard.html task detail panel. (1) CSS: 10 new style rules (.release-picks-list, .release-pick-entry, .release-pick-branch, .release-pick-status with 9 color variants for each status, .release-pick-task-link, .release-pick-pr-link, .release-pick-next-action, .release-pick-backport-of). (2) JS helpers: releasePickNextAction(status) maps all 9 ReleasePick states to human-readable next-action hints; renderReleasePicksSection(picksData, identifier, projectId) builds the compact section HTML showing backport-of info, per-branch entries (branch chip, colored status badge, clickable child-task link, PR link with target=_blank, next-action hint), and '+ Add Release Picks' button; openAddReleasePicksModal(identifier, projectId) dispatches oompah:open-add-release-picks custom event for TASK-456.3 to consume. (3) openDetailPanel() modified to kick off /release-picks fetch in parallel with /detail fetch (.catch(()=>null) graceful degradation), awaits and parses the result, then calls renderReleasePicksSection() before the Comments block.
---

author: oompah
created: 2026-06-08 22:32
---
Verification: 28/28 tests pass in tests/test_dashboard_release_picks_section.py covering: 8 CSS class assertions, 4 releasePickNextAction() tests, 9 renderReleasePicksSection() tests, 2 openAddReleasePicksModal() tests, 5 openDetailPanel() integration tests. No regressions in test_open_detail_panel_network_error.py, test_dashboard_comment_posting.py, test_dashboard_refresh.py, test_server_release_picks.py (pre-existing TASK-456.4 matrix 404 test failure unrelated to this PR). Pushed to origin/epic-TASK-456 at commit ed0f473.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added compact Release Picks section to the task detail panel (dashboard.html). Confirmed NOT a duplicate — distinct from TASK-456.3 (modal), TASK-456.4 (epic matrix), TASK-456.5 (validation states). Implemented: CSS styles for all section elements with 9 per-status colour variants; releasePickNextAction() helper mapping all lifecycle states to operator hints; renderReleasePicksSection() building the full HTML (backport-of link, per-branch rows with branch chip / status badge / child-task link / PR link / next-action hint, empty state, Add Release Picks button); openAddReleasePicksModal() placeholder that dispatches oompah:open-add-release-picks for TASK-456.3; openDetailPanel() modified to fetch /release-picks in parallel with graceful degradation. 28 new tests, 0 regressions. Pushed to origin/epic-TASK-456 (commit ed0f473).
<!-- SECTION:FINAL_SUMMARY:END -->
