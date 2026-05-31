---
id: TASK-171
title: ModelProvider.model_capabilities field
status: Done
assignee: []
created_date: 2026-04-28 20:56
updated_date: 2026-04-29 02:22
labels:
- beads-migrated
dependencies: []
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-zlz.2
  state: closed
  parent_id: oompah-zlz
  dependencies: []
  branch_name: oompah-zlz.2
  target_branch: null
  url: null
  created_at: '2026-04-28T20:56:35Z'
  updated_at: '2026-04-29T02:22:44Z'
  closed_at: '2026-04-29T02:22:44Z'
parent: TASK-165
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add model_capabilities: dict[str, list[str]] to ModelProvider (e.g. {'gpt-4o-mini': ['text','image']}). Round-trip in to_dict/from_dict. Surface as editable column on the /providers page. Default capability when unset is ['text']. Tests for serialization and the providers PATCH endpoint.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: cceab4f7-15a7-4f0e-b17c-40ac43f77142
author: oompah
created: 2026-04-28T21:38:33Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 321d7909-48f9-4b73-a701-81e8fc9a0388
author: oompah
created: 2026-04-28T21:38:34Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6c1-f4a0-72a3-b78e-2b873182d50a
author: oompah
created: 2026-04-29T01:02:09Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6c1-f706-7403-9275-5b29a3dc3f77
author: oompah
created: 2026-04-29T01:02:09Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d4-8164-7708-8f29-368fa713b143
author: oompah
created: 2026-04-29T01:22:24Z

Agent completed successfully in 1216s (4777377 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d4-85d3-7a48-b5e6-b660af285909
author: oompah
created: 2026-04-29T01:22:25Z

Agent completed without closing this issue (1216s (4777377 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d5-03d7-77d7-8087-8d690a77d02a
author: oompah
created: 2026-04-29T01:22:58Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d5-0d7e-7553-a008-8b31166e3fc2
author: oompah
created: 2026-04-29T01:23:00Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d8-e139-74c2-b25f-851f0f66ad85
author: oompah
created: 2026-04-29T01:27:11Z

Agent completed successfully in 253s (476787 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d9-44ac-7ad1-8a8f-ec5cf6bffe7a
author: oompah
created: 2026-04-29T01:27:36Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6d9-511d-7cec-8f88-f23e8109e92d
author: oompah
created: 2026-04-29T01:27:40Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6da-e254-7340-a107-2f2a502584fd
author: oompah
created: 2026-04-29T01:29:22Z

Agent completed successfully in 103s (104353 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6da-e66f-7ea6-a794-a626d23f5c4c
author: oompah
created: 2026-04-29T01:29:23Z

Agent completed 3 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6dc-7935-7134-86aa-a5a970fbf523
author: oompah
created: 2026-04-29T01:31:06Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6dc-aa3b-774f-85ff-220c5daf4f96
author: oompah
created: 2026-04-29T01:31:19Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6df-f31f-76d2-8223-cf6398113d0e
author: oompah
created: 2026-04-29T01:34:54Z

Agent completed successfully in 234s (286214 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6df-f727-75f7-922e-fbd4acd36058
author: oompah
created: 2026-04-29T01:34:55Z

Agent completed 4 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e2-fbe0-780e-8a99-efc6035d451d
author: oompah
created: 2026-04-29T01:38:13Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e3-0301-7ccd-8969-3e29723e134a
author: oompah
created: 2026-04-29T01:38:15Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e6-411d-734b-8461-1faf00b85b61
author: oompah
created: 2026-04-29T01:41:47Z

Agent completed successfully in 215s (275911 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e6-460a-7b0c-8625-5d2473b884cc
author: oompah
created: 2026-04-29T01:41:49Z

Agent completed 5 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6ea-0f3f-79c0-ae39-2c4d5d73c6f1
author: oompah
created: 2026-04-29T01:45:57Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6ea-34a5-7da4-8454-d15d3ffb4981
author: oompah
created: 2026-04-29T01:46:06Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6ef-431b-777d-99f0-e8393acfbcbd
author: oompah
created: 2026-04-29T01:51:38Z

Agent completed successfully in 341s (405251 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6ef-4eba-7134-8f63-bfe9180158bd
author: oompah
created: 2026-04-29T01:51:41Z

Agent completed without closing this issue (341s (405251 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f0-1b55-7e3c-ba9b-65e9ce91c518
author: oompah
created: 2026-04-29T01:52:33Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f0-6c6d-7956-a088-88a604ba8782
author: oompah
created: 2026-04-29T01:52:54Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f5-6fa7-7441-b799-a3becd29e1d6
author: oompah
created: 2026-04-29T01:58:22Z

Agent completed successfully in 352s (265639 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f5-7a6a-7ac1-b242-e8c73d3e761d
author: oompah
created: 2026-04-29T01:58:25Z

Agent completed without closing this issue (352s (265639 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (1/3).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f5-ebfe-705d-a052-c1ef88984601
author: oompah
created: 2026-04-29T01:58:54Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6f5-f986-7d42-b196-3a186d033487
author: oompah
created: 2026-04-29T01:58:58Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6fb-a56f-7c06-82b3-c9fcce41f89f
author: oompah
created: 2026-04-29T02:05:09Z

Agent completed successfully in 373s (338967 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6fc-bce5-7f17-a582-85b119edeaae
author: oompah
created: 2026-04-29T02:06:21Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6fc-d13e-793f-9ef1-88c593d8bd39
author: oompah
created: 2026-04-29T02:06:26Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd700-e21f-7868-ad22-0dacddf032ea
author: oompah
created: 2026-04-29T02:10:53Z

Agent completed successfully in 278s (316924 tokens)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd700-f1a7-7493-b5dd-ffbb8a40bdb6
author: oompah
created: 2026-04-29T02:10:57Z

Agent completed 3 times without closing this issue. Deferring — needs human attention.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
