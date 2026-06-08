---
id: TASK-456.3
title: Build Add Release Picks modal
status: Done
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 22:37'
labels:
  - task
dependencies:
  - TASK-456.1
parent_task_id: TASK-456
priority: high
ordinal: 105000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a modal for choosing cherry-pick strategy, source commit mode, and target release branches from configured project branches. Support scheduling before source merge and creating picks after merge.
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
created: 2026-06-08 22:16
---
Understanding: This is NOT a duplicate. Previous Duplicate Investigator runs also found no duplicate. TASK-456.3 is a unique frontend task building the 'Add Release Picks' modal UI as part of the TASK-456 epic. The blocker TASK-456.1 (release-pick API) is Done. This task requires building a modal with: (1) cherry-pick strategy selection, (2) source commit mode, (3) target release branch selection from configured project branches, (4) scheduling support (before source merge), and (5) pick creation (after merge). Plan: explore existing UI components, understand project structure, implement the modal with tests.
---

author: oompah
created: 2026-06-08 22:21
---
Discovery: NOT a duplicate. Confirmed unique. Codebase exploration complete. Key findings: (1) dashboard.html has a dialog-overlay pattern used for the create-issue dialog; (2) TASK-456.1 API provides GET/PATCH /api/v1/issues/{id}/release-picks; (3) GET /api/v1/projects/{id} returns branches list; (4) ReleasePick.WAITING = schedule-before-merge, ReleasePick.TASK_CREATED = create-now-after-merge; (5) Tests follow the pattern of reading the script block from dashboard.html and verifying functions. Plan: add modal HTML (dialog-overlay), add three JS functions (openAddReleasePicksDialog, closeAddReleasePicksDialog, submitAddReleasePicksDialog), add tests in test_add_release_picks_modal.py.
---

author: oompah
created: 2026-06-08 22:37
---
Implementation: Added the Add Release Picks modal to dashboard.html. (1) Modal HTML (dialog-overlay): cherry-pick strategy select (pr_commits/single/manual), source-commit-mode radio group (schedule→waiting / create→task_created), target branch checklist loaded from /api/v1/projects/{id}, error div. (2) Three JS functions: openAddReleasePicksDialog() fetches project branches + existing picks in parallel, renders checkbox list excluding default branch, marks already-tracked branches as disabled; closeAddReleasePicksDialog() clears state and removes open class; submitAddReleasePicksDialog() collects selected branches, maps mode to status, builds backports list, calls PATCH /api/v1/issues/{id}/release-picks, shows inline errors, refreshes detail panel on success. (3) Event bridge: document.addEventListener('oompah:open-add-release-picks') forwards to openAddReleasePicksDialog so TASK-456.2's openAddReleasePicksModal stub integrates correctly. (4) Fixed release_pick_schema.py: added SKIPPED status that was expected by tests but missing from HEAD.
---

author: oompah
created: 2026-06-08 22:37
---
Verification: 57 new tests in tests/test_add_release_picks_modal.py — all pass. Tests cover HTML structure (16), event bridge (4), JS function definitions (6), openAddReleasePicksDialog body (10), closeAddReleasePicksDialog body (4), submitAddReleasePicksDialog body (17). Full suite of 281 release-picks tests (test_add_release_picks_modal + test_dashboard_release_picks_section + test_server_release_picks + test_release_pick_api + test_release_pick_schema) passes with 0 failures. Committed and pushed to origin/epic-TASK-456 (commit 1278f50).
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Delivered Add Release Picks modal in dashboard.html. Modal has: cherry-pick strategy select (pr_commits/single/manual), source-commit-mode radios (schedule before merge → waiting status / create now → task_created status), target release branch checklist fetched from project config (default branch excluded, already-tracked branches shown as disabled). Three JS functions (openAddReleasePicksDialog, closeAddReleasePicksDialog, submitAddReleasePicksDialog) plus an event bridge that listens for oompah:open-add-release-picks custom event from TASK-456.2's stub. PATCH /api/v1/issues/{id}/release-picks call on submit. Also fixed release_pick_schema.py SKIPPED status that was missing from HEAD. 57 new tests, 281 release-picks tests total pass. Pushed to origin/epic-TASK-456.
<!-- SECTION:FINAL_SUMMARY:END -->
