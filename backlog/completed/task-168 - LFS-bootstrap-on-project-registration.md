---
id: TASK-168
title: LFS bootstrap on project registration
status: Done
assignee: []
created_date: 2026-04-28 20:56
updated_date: 2026-04-29 02:19
labels:
- beads-migrated
dependencies:
- TASK-167
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-a9c.2
  state: closed
  parent_id: oompah-a9c
  dependencies:
  - oompah-a9c.1
  branch_name: oompah-a9c.2
  target_branch: null
  url: null
  created_at: '2026-04-28T20:56:33Z'
  updated_at: '2026-04-29T02:19:21Z'
  closed_at: '2026-04-29T02:19:21Z'
parent: TASK-163
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Project registration runs git lfs install --local idempotently, writes .oompah/attachments/.gitattributes with LFS filters for png/jpg/jpeg/gif/webp/pdf/mp3/wav/m4a/mp4, and stages the file. When git lfs is unavailable, registration succeeds with a warning and Project.lfs_available is set to False. Adds lfs_available field to Project. Tests cover idempotency and the no-LFS-installed path.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
