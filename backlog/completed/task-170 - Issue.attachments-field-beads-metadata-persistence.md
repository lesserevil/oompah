---
id: TASK-170
title: Issue.attachments field + beads metadata persistence
status: Done
assignee: []
created_date: 2026-04-28 20:56
updated_date: 2026-04-29 02:21
labels:
- beads-migrated
dependencies:
- TASK-167
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-zlz.1
  state: closed
  parent_id: oompah-zlz
  dependencies:
  - oompah-a9c.1
  branch_name: oompah-zlz.1
  target_branch: null
  url: null
  created_at: '2026-04-28T20:56:34Z'
  updated_at: '2026-04-29T02:21:32Z'
  closed_at: '2026-04-29T02:21:32Z'
parent: TASK-165
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add attachments: list[str] to Issue (oompah/models.py). Tracker parses metadata['oompah.attachments'] in _parse_issue and exposes a set_attachments(identifier, list[Attachment]) writer. Sidecar manifest at .oompah/attachments/<id>/manifest.json kept in sync as a dashboard-side cache. Tests round-trip metadata read+write and confirm the sidecar stays consistent.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019dd6e2-ab49-76ae-981a-4b5b1868ea27
author: oompah
created: 2026-04-29T01:37:52Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e2-b140-785c-a58d-03392db26973
author: oompah
created: 2026-04-29T01:37:54Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e4-1bc8-7b79-9eff-8d9a20a18ce5
author: oompah
created: 2026-04-29T01:39:27Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e4-20c1-7a44-b39a-ae64c01f3e0d
author: oompah
created: 2026-04-29T01:39:28Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
