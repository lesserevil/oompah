---
id: TASK-167
title: Create AttachmentStore + Attachment dataclass
status: Done
assignee: []
created_date: 2026-04-28 20:56
updated_date: 2026-04-29 02:16
labels:
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-a9c.1
  state: closed
  parent_id: oompah-a9c
  dependencies: []
  branch_name: oompah-a9c.1
  target_branch: null
  url: null
  created_at: '2026-04-28T20:56:32Z'
  updated_at: '2026-04-29T02:16:04Z'
  closed_at: '2026-04-29T02:16:04Z'
parent: TASK-163
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add oompah/attachments.py with an AttachmentStore class (add/list/open/absolute/ensure_lfs_configured/commit) and an Attachment dataclass (path, mime_type, size, created_at, generated, turn). Files are written under .oompah/attachments/<issue>/ with names <sha-prefix>-<original>. Includes tests/test_attachments.py covering CRUD, mime whitelist, size limits, and per-issue cap. See docs/multimodal-attachments.md §Storage layer.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 0b071700-a596-42fb-b503-e8335e7beb82
author: oompah
created: 2026-04-28T21:38:32Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 895ed03d-ffca-4abb-ae24-0c5d2caf2a20
author: oompah
created: 2026-04-28T21:38:33Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6c1-dcac-71dc-ae96-615f60863474
author: oompah
created: 2026-04-29T01:02:02Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6c1-df5e-7989-b8c5-720a2d3f9310
author: oompah
created: 2026-04-29T01:02:03Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6cf-2fff-736e-b2e6-8f69e4a9a728
author: oompah
created: 2026-04-29T01:16:36Z

Agent completed successfully in 872s (2272724 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6cf-3c43-7d2f-88e7-ea51e23a0e78
author: oompah
created: 2026-04-29T01:16:39Z

Agent completed without closing this issue (872s (2272724 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6cf-725f-78b6-8ad6-0e0c7a52c6cf
author: oompah
created: 2026-04-29T01:16:53Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6cf-777e-76d6-8b6a-576a3de9cc9d
author: oompah
created: 2026-04-29T01:16:54Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d2-6dc1-7cd9-b03d-8b19afffe547
author: oompah
created: 2026-04-29T01:20:08Z

Agent completed successfully in 195s (529976 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d2-869c-76be-ba61-f6374a7a0720
author: oompah
created: 2026-04-29T01:20:14Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d2-a496-7c58-945f-ef6cca371eb0
author: oompah
created: 2026-04-29T01:20:22Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d3-f6ed-751c-9b3c-26c9c96c1d9a
author: oompah
created: 2026-04-29T01:21:49Z

Agent completed successfully in 94s (75454 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d3-ff5f-7140-9c19-02f96959cacf
author: oompah
created: 2026-04-29T01:21:51Z

Agent completed 3 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6dc-58ec-736e-b29b-c90d2a269e75
author: oompah
created: 2026-04-29T01:30:58Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6dc-85b6-7109-89bd-05c471a10fd4
author: oompah
created: 2026-04-29T01:31:10Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6dd-9595-72d2-b1ed-645935fa421d
author: oompah
created: 2026-04-29T01:32:19Z

Agent completed successfully in 79s (124974 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6dd-99aa-7294-a5f2-06565679ed6f
author: oompah
created: 2026-04-29T01:32:20Z

Agent completed 4 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e2-830e-7518-a1c8-d94c18547c6d
author: oompah
created: 2026-04-29T01:37:42Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e2-9969-7288-9fab-390631f9773b
author: oompah
created: 2026-04-29T01:37:48Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e6-c72c-7eff-bc84-056e25b9332d
author: oompah
created: 2026-04-29T01:42:22Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e6-c999-7271-950a-0758dbf47c57
author: oompah
created: 2026-04-29T01:42:22Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e9-f181-7cd1-b5fd-b4ded4edec2b
author: oompah
created: 2026-04-29T01:45:49Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e9-fba9-729b-833c-58b89e127ddb
author: oompah
created: 2026-04-29T01:45:52Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6eb-2663-7887-9f9f-9ae457461302
author: oompah
created: 2026-04-29T01:47:08Z

Agent completed successfully in 79s (69964 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6eb-3208-70ea-899e-dcd051c76179
author: oompah
created: 2026-04-29T01:47:11Z

Agent completed without closing this issue (79s (69964 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6eb-7525-7c15-ad04-d39c8700cef6
author: oompah
created: 2026-04-29T01:47:28Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6ef-e972-7aa6-ad2d-b00b4d634042
author: oompah
created: 2026-04-29T01:52:20Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f0-5192-7b1b-a259-f8074163660e
author: oompah
created: 2026-04-29T01:52:47Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f2-699c-78c2-ba24-abd9aa5dd8d4
author: oompah
created: 2026-04-29T01:55:04Z

Agent completed successfully in 153s (246572 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f2-7446-7478-900c-6d98df7da60d
author: oompah
created: 2026-04-29T01:55:07Z

Agent completed without closing this issue (153s (246572 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f2-ed38-714c-924d-637ea265d560
author: oompah
created: 2026-04-29T01:55:38Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f3-205b-7dda-9a45-ad6deeadeefc
author: oompah
created: 2026-04-29T01:55:51Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f4-5e90-718e-9623-404e1f1a8727
author: oompah
created: 2026-04-29T01:57:12Z

Agent completed successfully in 105s (283865 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f5-03b0-760e-902c-2a796b39ecc5
author: oompah
created: 2026-04-29T01:57:55Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f5-1003-73d0-97bc-e74f1e81a892
author: oompah
created: 2026-04-29T01:57:58Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f7-5d70-70bf-9c16-4a685ec6b3ab
author: oompah
created: 2026-04-29T02:00:29Z

Agent completed successfully in 139s (122321 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f7-67bd-78e9-b066-db01afe37538
author: oompah
created: 2026-04-29T02:00:31Z

Agent completed 3 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6fb-49ce-7b27-9d32-0a4733c8001c
author: oompah
created: 2026-04-29T02:04:46Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6fb-5ba0-77d3-91b8-25abca7003f0
author: oompah
created: 2026-04-29T02:04:50Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6fc-7d0c-74a7-88ca-f6d0fee824a1
author: oompah
created: 2026-04-29T02:06:05Z

Agent completed successfully in 76s (96069 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6fc-877a-7a83-bd00-0eb95fbc8df8
author: oompah
created: 2026-04-29T02:06:07Z

Agent completed 4 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
