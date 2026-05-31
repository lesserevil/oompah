---
id: TASK-189
title: Drop OOMPAH_ATTACHMENTS feature flag
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 03:29
labels:
- beads-migrated
dependencies:
- TASK-168
- TASK-180
- TASK-188
- TASK-176
priority: low
ordinal: 1000
type: task
beads:
  id: oompah-j12
  state: closed
  parent_id: null
  dependencies:
  - oompah-a9c.2
  - oompah-e6y.4
  - oompah-xho.8
  - oompah-zlz.7
  branch_name: oompah-j12
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:37Z'
  updated_at: '2026-04-29T03:29:22Z'
  closed_at: '2026-04-29T03:29:22Z'
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Once Phases 1-4 are stable in dogfood, remove the OOMPAH_ATTACHMENTS gate. Update .env.example and README to reflect that attachments are always on (when git lfs is available). Depends on all four phases.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019dd73f-3a59-71e0-a8cf-2f0ac94a07a8
author: oompah
created: 2026-04-29T03:18:58Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd73f-4424-7a7b-bd59-bea50a588feb
author: oompah
created: 2026-04-29T03:19:01Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd744-e2d5-7f1b-b194-f25cd5e1890e
author: oompah
created: 2026-04-29T03:25:09Z

Agent completed successfully in 371s (1666444 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd744-f0ed-7157-af03-38b3716277aa
author: oompah
created: 2026-04-29T03:25:13Z

Agent completed without closing this issue (371s (1666444 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd745-4697-7182-a804-40a1da8b78f7
author: oompah
created: 2026-04-29T03:25:35Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd745-4ed5-757e-85cb-d9d42e323285
author: oompah
created: 2026-04-29T03:25:37Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd747-f024-71ad-8357-6ecb12235941
author: oompah
created: 2026-04-29T03:28:29Z

Verified the implementation from the previous agent session. All changes are correct and complete:

1. **config.py**: Removed  field from  and  env var parsing from
2. **server.py**: Removed feature gate checks from , , and  endpoints
3. **.env.example**: Removed the  entry
4. **docs/multimodal-attachments.md**: Updated Rollout section to reflect that the flag has been removed
5. **tests/test_config.py**: Replaced 4 flag-specific tests with a regression guard asserting the field no longer exists
6. **tests/test_server_attachments.py**: Removed 2 'disabled' tests and the `attachments_enabled` kwarg

Tests pass: 12/12 attachment-related tests pass. The 2 pre-existing test failures (test_from_workflow_defaults, test_from_workflow_custom) are unrelated to this change (they exist on the parent commit too). Closing.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd749-15d2-79eb-8cad-eb4b6692e983
author: oompah
created: 2026-04-29T03:29:44Z

Agent completed successfully in 255s (760031 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd749-4eb3-7612-9959-2185ee2d560e
author: oompah
created: 2026-04-29T03:29:59Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd749-5714-7c67-8bb7-10f1b7b22c64
author: oompah
created: 2026-04-29T03:30:01Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd74a-0942-7952-855a-c0d1c063c591
author: oompah
created: 2026-04-29T03:30:47Z

Agent completed successfully in 48s (44613 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd74a-1768-7603-83e4-4ebffb9c5e90
author: oompah
created: 2026-04-29T03:30:50Z

Agent completed 3 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd753-70fe-7c83-bd60-98a914bf77bc
author: oompah
created: 2026-04-29T03:41:03Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd753-8746-7e77-a807-3590ffaa3d2a
author: oompah
created: 2026-04-29T03:41:09Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd756-0374-79b0-b057-e15444e3810a
author: oompah
created: 2026-04-29T03:43:52Z

Agent completed successfully in 169s (298915 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd756-1243-7829-8fcf-ed3e73132e0d
author: oompah
created: 2026-04-29T03:43:55Z

Agent completed 4 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
