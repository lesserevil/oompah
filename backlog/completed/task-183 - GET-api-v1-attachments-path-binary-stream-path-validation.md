---
id: TASK-183
title: GET /api/v1/attachments/{path} (binary stream + path validation)
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 02:40
labels:
- beads-migrated
dependencies:
- TASK-167
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-xho.3
  state: closed
  parent_id: oompah-xho
  dependencies:
  - oompah-a9c.1
  branch_name: oompah-xho.3
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:27Z'
  updated_at: '2026-04-29T02:40:52Z'
  closed_at: '2026-04-29T02:40:52Z'
parent: TASK-166
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Streams the LFS-resolved bytes with the right Content-Type. Path is validated to be under .oompah/attachments/ for some known project — anything else returns 404. SVG content is sanitized (scripts stripped) before serving. Tests: traversal attempts (../, absolute paths, symlinks), SVG with embedded <script>, and the happy path.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
