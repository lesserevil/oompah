---
id: TASK-184
title: DELETE /api/v1/attachments/{path}
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 02:40
labels:
- beads-migrated
dependencies:
- TASK-181
priority: low
ordinal: 1000
type: task
beads:
  id: oompah-xho.4
  state: closed
  parent_id: oompah-xho
  dependencies:
  - oompah-xho.1
  branch_name: oompah-xho.4
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:28Z'
  updated_at: '2026-04-29T02:40:55Z'
  closed_at: '2026-04-29T02:40:55Z'
parent: TASK-166
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Removes the path from the issue's metadata and creates a git commit removing the file. User-added attachments are removable freely; generated attachments require an explicit 'force=generated' query param. Tests cover both branches and the commit content.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
