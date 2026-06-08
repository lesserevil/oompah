---
id: TASK-456.3
title: Build Add Release Picks modal
status: In Progress
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 22:21'
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
<!-- COMMENTS:END -->
