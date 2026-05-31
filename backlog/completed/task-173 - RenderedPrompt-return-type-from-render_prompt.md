---
id: TASK-173
title: RenderedPrompt return type from render_prompt
status: Done
assignee: []
created_date: 2026-04-28 20:56
updated_date: 2026-04-29 02:25
labels:
- beads-migrated
dependencies:
- TASK-167
- TASK-168
- TASK-170
- TASK-172
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-zlz.4
  state: closed
  parent_id: oompah-zlz
  dependencies:
  - oompah-a9c.1
  - oompah-a9c.2
  - oompah-zlz.1
  - oompah-zlz.3
  branch_name: oompah-zlz.4
  target_branch: null
  url: null
  created_at: '2026-04-28T20:56:36Z'
  updated_at: '2026-04-29T02:25:56Z'
  closed_at: '2026-04-29T02:25:56Z'
parent: TASK-165
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Change render_prompt to return RenderedPrompt(text, parts). When the resolved model supports image/audio, build OpenAI-style content parts with type=image_url (data URLs from LFS-pulled bytes) or type=input_audio. Unsupported attachments get a 'not sent' note in the text portion. Honour per-attachment 25 MB cap and per-prompt 20 MB total — elide overflow with a warning. Tests cover both rendering modes and the elision path.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 019dd6e3-17e4-7f2a-8646-1cd9e7b1a9c1
author: oompah
created: 2026-04-29T01:38:20Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e3-56a3-7c48-b966-bbb2ea0eb2ad
author: oompah
created: 2026-04-29T01:38:36Z

Agent dispatched (profile: standard)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e5-9cad-7d2b-9046-0f3b2782b977
author: oompah
created: 2026-04-29T01:41:05Z

Agent stalled 1 time(s) (167s (330057 tokens)). Escalating from 'standard' to 'deep'. Retrying in 10s (attempt #1)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e6-0378-77a1-b81c-04188378b769
author: oompah
created: 2026-04-29T01:41:32Z

Agent dispatched (profile: deep)
<!-- COMMENT:END -->
<!-- COMMENT:BEGIN -->
index: 019dd6e6-110d-74e9-b520-2a2cee55cdfa
author: oompah
created: 2026-04-29T01:41:35Z

Focus: Event Queue Pipeline Specialist
<!-- COMMENT:END -->
<!-- COMMENTS:END -->
