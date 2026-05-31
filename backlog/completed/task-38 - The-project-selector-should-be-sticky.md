---
id: TASK-38
title: The project selector should be 'sticky'
status: Done
assignee: []
created_date: 2026-03-07 02:57
updated_date: 2026-03-07 04:55
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: low
ordinal: 1000
type: task
beads:
  id: umpah-amw
  state: closed
  parent_id: null
  dependencies: []
  branch_name: umpah-amw
  target_branch: null
  url: null
  created_at: '2026-03-07T02:57:00Z'
  updated_at: '2026-03-07T04:55:33Z'
  closed_at: '2026-03-07T04:55:33Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
If a project is selected in the project selector pulldown, all pages which have project specific information should respect the setting. The project selector should be visible on all of these pages, and the project selector's setting should stay selected between pages.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: f5f800c0-eb20-47c3-9e93-cdb2a2dcfc7f
author: oompah
created: 2026-03-07T04:30:52Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: abbd44ec-f9c3-47a9-9e1f-e02d7244fe9b
author: oompah
created: 2026-03-07T04:30:55Z

Focus: Software Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 66cd9151-1918-4f6e-a8f5-e2d086d2981a
author: Shawn Edwards
created: 2026-03-07T04:32:23Z

I understand the issue: The project selector dropdown exists on the main dashboard but is not present on other pages (Providers, Projects, Foci, Reviews). When a user selects a project on the dashboard and navigates to another page, the selection is lost. The fix requires: 1) Adding the project selector to all pages that have project-specific information, 2) Persisting the selected project in localStorage so it stays selected when navigating between pages. My plan is to modify the server.py HTML strings to add a project selector to the toolbar on each page and use localStorage to persist/restore the selection.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d356b61e-6f78-406c-9bae-79cddb120109
author: Shawn Edwards
created: 2026-03-07T04:34:05Z

Found the relevant code: The project selector exists only on the main dashboard (/) and is populated dynamically via WebSocket. When a user navigates to /providers, /projects-manage, /foci, or /reviews, the project selector is gone. There's also no localStorage persistence - project selection is lost between page loads. Fix plan: 1) Add localStorage save/restore for project selection on the dashboard. 2) Add a sticky project selector to the toolbar on pages with project-specific content (Reviews especially). The selector on secondary pages will use the REST API to fetch projects and persist via localStorage using a shared key 'oompah_selected_project'.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 41fe88a7-e75a-4d29-b560-a926109d069b
author: Shawn Edwards
created: 2026-03-07T04:53:55Z

Implemented the sticky project selector. Changes to oompah/server.py: 1) Dashboard now saves selected project to localStorage key 'oompah_selected_project' on change and restores it when the dropdown is populated. 2) Added project selector dropdown to all 4 secondary pages (Providers, Projects, Foci, Reviews) - each fetches projects from /api/v1/projects and shows the saved selection. All pages share the same localStorage key so navigation maintains the selection. The selector is hidden when no projects are configured.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4378205d-a454-4ca3-8633-3654a6c43ca7
author: Shawn Edwards
created: 2026-03-07T04:54:16Z

Verification: All 186 tests pass. No regressions.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 1f3aefbf-4aba-4956-b4dc-67304db33b91
author: Shawn Edwards
created: 2026-03-07T04:55:19Z

PR created: https://github.com/lesserevil/oompah/pull/11

Summary of what was delivered:
- Dashboard project selector now saves selection to localStorage on change
- Dashboard restores saved selection when project list loads via WebSocket
- Added sticky project selector to all secondary pages: Providers, Projects, Foci, Reviews
- All pages share localStorage key 'oompah_selected_project' for consistent cross-page persistence
- Selector hidden when no projects configured (single-project/legacy mode)
- All 186 tests pass
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f5ff3411-db1e-4d15-946b-b45eddd87597
author: oompah
created: 2026-03-07T04:55:52Z

Agent completed successfully in 1499s (9872531 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
