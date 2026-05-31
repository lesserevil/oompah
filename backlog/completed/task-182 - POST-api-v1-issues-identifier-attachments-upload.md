---
id: TASK-182
title: POST /api/v1/issues/{identifier}/attachments (upload)
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 02:40
labels:
- beads-migrated
dependencies:
- TASK-167
- TASK-181
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-xho.2
  state: closed
  parent_id: oompah-xho
  dependencies:
  - oompah-a9c.1
  - oompah-xho.1
  branch_name: oompah-xho.2
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:26Z'
  updated_at: '2026-04-29T02:40:49Z'
  closed_at: '2026-04-29T02:40:49Z'
parent: TASK-166
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Multipart upload: reject on mime not in whitelist (415), per-attachment cap exceeded (413), per-issue cap exceeded (413). On success, hand to AttachmentStore.add, update metadata, commit, return the new record. Tests for each rejection path and the success path.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
