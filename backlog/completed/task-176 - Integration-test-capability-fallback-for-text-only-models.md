---
id: TASK-176
title: 'Integration test: capability fallback for text-only models'
status: Done
assignee: []
created_date: 2026-04-28 20:56
updated_date: 2026-04-29 02:29
labels:
- beads-migrated
dependencies:
- TASK-175
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-zlz.7
  state: closed
  parent_id: oompah-zlz
  dependencies:
  - oompah-zlz.6
  branch_name: oompah-zlz.7
  target_branch: null
  url: null
  created_at: '2026-04-28T20:56:37Z'
  updated_at: '2026-04-29T02:29:53Z'
  closed_at: '2026-04-29T02:29:53Z'
parent: TASK-165
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
End-to-end test that an issue with two image attachments dispatched to a text-only model produces a string prompt listing the attachment paths with 'not sent — model lacks vision' notes, no API failure. A second test confirms a multimodal model receives a content array with two image_url parts.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
