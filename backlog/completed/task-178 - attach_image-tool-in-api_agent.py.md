---
id: TASK-178
title: attach_image tool in api_agent.py
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 02:34
labels:
- beads-migrated
dependencies:
- TASK-177
- TASK-174
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-e6y.2
  state: closed
  parent_id: oompah-e6y
  dependencies:
  - oompah-e6y.1
  - oompah-zlz.5
  branch_name: oompah-e6y.2
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:23Z'
  updated_at: '2026-04-29T02:34:16Z'
  closed_at: '2026-04-29T02:34:16Z'
parent: TASK-164
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Register an attach_image(filename, content_base64, caption?) tool that decodes the bytes, validates mime + size, and writes under .oompah/attachments/<issue>/outputs/<turn>-<sha>-<filename>. Tool is only registered when (a) the resolved model has 'image' capability and (b) the active focus has allow_image_output=True. Returns the canonical relative path. Tests: tool registration gating, tool roundtrip, oversize rejection.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
