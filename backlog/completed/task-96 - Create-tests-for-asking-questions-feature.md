---
id: TASK-96
title: Create tests for asking questions feature
status: Done
assignee: []
created_date: 2026-03-08 20:08
updated_date: 2026-03-08 20:56
labels:
- archive:yes
- merged
- beads-migrated
dependencies: []
priority: high
ordinal: 1000
type: task
beads:
  id: oompah-b8k
  state: closed
  parent_id: oompah-de9
  dependencies: []
  branch_name: oompah-b8k
  target_branch: null
  url: null
  created_at: '2026-03-08T20:08:32Z'
  updated_at: '2026-03-08T20:56:12Z'
  closed_at: '2026-03-08T20:56:12Z'
parent: TASK-74
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create tests to ensure the asking questions feature works as expected
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 61f587b0-a70a-4ce6-b14b-027b64a42249
author: oompah
created: 2026-03-08T20:23:40Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 8e81fd6c-7ef0-4a50-bca1-ea9f2575d8bc
author: oompah
created: 2026-03-08T20:23:41Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 973cfa24-d5bb-495e-abc0-9fb9a21d82c6
author: oompah
created: 2026-03-08T20:25:10Z

I understand the issue: Create tests for the 'asking questions' feature. Based on the epic (oompah-de9), the feature should allow agents to ask questions in the comments thread, mark the issue with an 'asking_question' label, move the task from 'in_progress' to 'open', and stop the agent. Issues with the 'asking_question' label must not be dispatched. Once the user answers in comments, the 'asking_question' label should be removed so the system can pick it back up. My plan: 1) Examine the related implementation task (oompah-055) to see what code exists or needs to exist, 2) Write comprehensive tests covering: dispatch prevention for issues with asking_question label, label management, comment-based question/answer flow, and orchestrator behavior.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 26401d41-2c3f-4bea-8b0e-1ac51a797f5b
author: oompah
created: 2026-03-08T20:25:48Z

Found the relevant code: The asking questions feature is defined in the epic (oompah-de9) but NOT yet implemented in the codebase. The implementation task (oompah-055) is in progress. The feature requires: 1) _should_dispatch to gate on 'asking_question' label, 2) A mechanism for agents to ask questions (comment + label + move to open), 3) Auto-removal of asking_question label when a user answers. I'll write tests that define this behavior as TDD-style specifications, testing both what exists (dispatch gating via label) and what needs to be added (question/answer flow).
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d47496b2-5b27-4a1e-9750-96afd6eef915
author: oompah
created: 2026-03-08T20:29:33Z

Agent failed: HTTP 429 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"{'error': 'Priority-based rate limit exceeded. Priority: dev, Rate limit type: tokens, Remaining: -522642, Model saturation: 70.7%'}","type":"None","param":"None","code":"429"}}. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4c5ff3bb-b1d8-4959-9f46-25fadf8ac08f
author: oompah
created: 2026-03-08T20:29:44Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6644e339-c1f8-438c-b966-06511642c421
author: oompah
created: 2026-03-08T20:29:44Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 7e73e8e6-08c8-42b2-9d8b-7d8debeb0665
author: oompah
created: 2026-03-08T20:29:45Z

Agent failed: HTTP 429 from https://inference-api.nvidia.com/chat/completions: {"error":{"message":"{'error': 'Priority-based rate limit exceeded. Priority: dev, Rate limit type: tokens, Remaining: -1911665, Model saturation: 72.9%'}","type":"None","param":"None","code":"429"}}. Retrying in 20s (attempt #2)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 0a1a4778-35f5-4ad6-994c-2ad842180934
author: oompah
created: 2026-03-08T20:30:06Z

Retrying (attempt #2, agent: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 4c6533c6-05b5-4d15-97d0-d6eeab3e16bb
author: oompah
created: 2026-03-08T20:30:07Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 6834e8da-fb58-4dab-b8f1-2046b3d67ce7
author: oompah
created: 2026-03-08T20:50:03Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 5aafd7ba-ee01-4390-8c88-1ad389ec0625
author: oompah
created: 2026-03-08T20:50:04Z

Focus: Test Engineer
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: d8ffef32-1381-408e-a080-efb478316fba
author: oompah
created: 2026-03-08T20:52:52Z

Found the implementation: The ask_question feature was implemented in PR #34 (oompah-055) and merged to origin/main. I've rebased our branch onto origin/main and confirmed all 17 existing tests pass. Now I'll add comprehensive additional tests covering: (1) question formatting in comment with emoji/markdown, (2) tracker error handling during ask_question exit, (3) concurrent dispatch prevention for asking_question issues, (4) project-scoped tracker used correctly, (5) orchestrator state cleanup on ask_question, (6) ask_question with multiple tool calls in same message, (7) server cache invalidation on user answer, (8) empty text comment validation, (9) label removal error doesn't break comment posting.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: f94e46f1-d7d1-4804-a8fd-03e9fdfeddab
author: oompah
created: 2026-03-08T20:55:38Z

Implementation complete: Created tests/test_asking_questions.py with 39 comprehensive tests covering: (1) Tool definition contracts (description, parameter schema, not in _TOOL_DISPATCH), (2) Agent loop edge cases (long question, mixed tool calls, whitespace question, token counts), (3) Dispatch guard completeness (P0 bypass NOT allowed, paused state, both open/in_progress states, similar-but-not-equal labels), (4) Project-scoped exit handling (project tracker used, fallback comment, tracker errors don't raise, no retry scheduled, token accumulation), (5) Server edge cases (empty text 400, label removal failure doesn't fail comment, fetch_issue_detail failure handled, None result handled, cache invalidated, comment result returned, label removed exactly once, omitted author defaults to user), (6) ApiAgentResult field contracts, (7) Full lifecycle integration tests. All 56 tests (17 original + 39 new) pass.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 967f8eb8-666f-4de8-b2c6-af1c27f890dc
author: oompah
created: 2026-03-08T20:56:07Z

PR created: https://github.com/lesserevil/oompah/pull/36 — 39 new tests for the asking questions feature, all passing. 56 total tests for this feature (17 original + 39 new). No new failures introduced.
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 53d241c1-b6c3-4189-b8ea-66831382161f
author: oompah
created: 2026-03-08T20:56:13Z

Agent completed successfully in 369s (3549308 tokens)
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
