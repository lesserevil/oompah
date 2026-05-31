---
id: TASK-180
title: Write generated attachments back into beads metadata
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 02:36
labels:
- beads-migrated
dependencies:
- TASK-179
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-e6y.4
  state: closed
  parent_id: oompah-e6y
  dependencies:
  - oompah-e6y.3
  branch_name: oompah-e6y.4
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:24Z'
  updated_at: '2026-04-29T02:36:45Z'
  closed_at: '2026-04-29T02:36:45Z'
parent: TASK-164
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After the commit step, update the issue's metadata['oompah.attachments'] with one entry per generated file (generated=true, added_by='agent', added_at). Completion comment lists the artifacts. Tests cover the metadata diff and idempotency on retry.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
