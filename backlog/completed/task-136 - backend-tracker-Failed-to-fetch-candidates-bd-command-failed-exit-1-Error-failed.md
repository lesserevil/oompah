---
id: TASK-136
title: '[backend:tracker] Failed to fetch candidates: bd command failed (exit 1):
  Error: failed to open database: database "sq" not found on Dolt server at beads.horde.nvidia.com:3307


  This can happen when...'
status: Done
assignee: []
created_date: 2026-03-11 13:14
updated_date: 2026-03-11 14:03
labels:
- archive:yes
- bug
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: bug
beads:
  id: oompah-9m8
  state: closed
  parent_id: null
  dependencies: []
  branch_name: oompah-9m8
  target_branch: null
  url: null
  created_at: '2026-03-11T13:14:07Z'
  updated_at: '2026-03-11T14:03:20Z'
  closed_at: '2026-03-11T14:03:20Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Failed to fetch candidates: bd command failed (exit 1): Error: failed to open database: database "sq" not found on Dolt server at beads.horde.nvidia.com:3307

This can happen when:
  - The server is serving a different data directory than expected
  - The database has not been initialized yet

To initialize a new board:  bd init
To check server status:     bd doctor
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: aeb98ecb-5d27-47f2-9f82-5b665e8e630a
author: oompah
created: 2026-03-11T14:03:05Z

Agent dispatched (profile: default)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: a0ccc66b-4480-4c31-aba7-9cd89a04037d
author: oompah
created: 2026-03-11T14:03:06Z

Focus: Feature Developer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5bf0a75a-9b62-4fbe-b2c5-4039d85948f1
author: oompah
created: 2026-03-11T14:03:14Z

I understand the issue: [backend:tracker] Failed to fetch candidates: bd command failed (exit 1): Error: failed to open database: database "sq" not found on Dolt server at beads.horde.nvidia.com:3307. My plan is to investigate the cause of the error and implement a solution.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: b9fd94a7-7bea-4ce9-ae81-f6e03f285d1b
author: oompah
created: 2026-03-11T14:03:20Z

Agent completed successfully in 15s (28663 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
