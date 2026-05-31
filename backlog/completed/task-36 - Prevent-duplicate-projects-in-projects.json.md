---
id: TASK-36
title: Prevent duplicate projects in projects.json
status: Done
assignee: []
created_date: 2026-03-07 01:22
updated_date: 2026-03-07 01:52
labels:
- archive:yes
- bug
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: bug
beads:
  id: umpah-ebq
  state: closed
  parent_id: null
  dependencies: []
  branch_name: umpah-ebq
  target_branch: null
  url: null
  created_at: '2026-03-07T01:22:23Z'
  updated_at: '2026-03-07T01:52:01Z'
  closed_at: '2026-03-07T01:52:01Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Adding a project via the UI creates duplicate entries in .oompah/projects.json. The project-add endpoint must check for an existing project with the same repo_url before inserting. If a duplicate is found, reject the request or update the existing entry.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 335175d4-77d4-4408-b63e-e8ba1343d849
author: oompah
created: 2026-03-07T01:49:11Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 42e85d9e-1b09-426f-b423-ce86c4e27200
author: oompah
created: 2026-03-07T01:49:31Z

Focus: Bug Investigator & Fixer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7e62165c-c28b-46e8-8e55-5eb29f192a70
author: Shawn Edwards
created: 2026-03-07T01:50:28Z

I understand the issue: Adding a project via the UI creates duplicate entries in .oompah/projects.json because the project-add endpoint doesn't check for existing projects with the same repo_url. My plan is to: 1) Find the project-add endpoint code, 2) Reproduce the bug, 3) Add a duplicate check before inserting, 4) Verify with tests.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
