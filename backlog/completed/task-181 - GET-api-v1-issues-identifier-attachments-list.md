---
id: TASK-181
title: GET /api/v1/issues/{identifier}/attachments (list)
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 02:40
labels:
- beads-migrated
dependencies:
- TASK-167
- TASK-170
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-xho.1
  state: closed
  parent_id: oompah-xho
  dependencies:
  - oompah-a9c.1
  - oompah-zlz.1
  branch_name: oompah-xho.1
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:26Z'
  updated_at: '2026-04-29T02:40:47Z'
  closed_at: '2026-04-29T02:40:47Z'
parent: TASK-166
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Endpoint returns the list of Attachment records for an issue (read from beads metadata + sidecar manifest). Tests cover empty list, mixed user/generated, and unknown identifier returning 404.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
