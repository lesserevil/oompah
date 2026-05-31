---
id: TASK-188
title: Server integration tests for attachments endpoints
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 02:41
labels:
- beads-migrated
dependencies:
- TASK-182
- TASK-183
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-xho.8
  state: closed
  parent_id: oompah-xho
  dependencies:
  - oompah-xho.2
  - oompah-xho.3
  branch_name: oompah-xho.8
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:30Z'
  updated_at: '2026-04-29T02:41:00Z'
  closed_at: '2026-04-29T02:41:00Z'
parent: TASK-166
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
tests/test_server_attachments.py covering: list, upload happy + rejections, serve + path traversal, delete user vs generated, SVG sanitization. Uses a tmp git repo with LFS configured (skipped when git lfs unavailable in CI).
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
