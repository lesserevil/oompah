---
id: TASK-185
title: Kanban card thumbnails
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 02:46
labels:
- beads-migrated
dependencies:
- TASK-181
- TASK-183
priority: low
ordinal: 1000
type: task
beads:
  id: oompah-xho.5
  state: closed
  parent_id: oompah-xho
  dependencies:
  - oompah-xho.1
  - oompah-xho.3
  branch_name: oompah-xho.5
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:28Z'
  updated_at: '2026-04-29T02:46:12Z'
  closed_at: '2026-04-29T02:46:12Z'
parent: TASK-166
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
On dashboard.html kanban cards, render up to 3 image thumbnails when the issue has image attachments; '+N more' otherwise. Show a paperclip icon with count for non-image attachments. Thumbs come from /api/v1/attachments/{path}. Lazy-load to avoid hammering the endpoint.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
