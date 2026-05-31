---
id: TASK-175
title: 'Orchestrator wiring: pull LFS, pass attachments through renderer'
status: Done
assignee: []
created_date: 2026-04-28 20:56
updated_date: 2026-04-29 02:29
labels:
- beads-migrated
dependencies:
- TASK-170
- TASK-174
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-zlz.6
  state: closed
  parent_id: oompah-zlz
  dependencies:
  - oompah-zlz.1
  - oompah-zlz.5
  branch_name: oompah-zlz.6
  target_branch: null
  url: null
  created_at: '2026-04-28T20:56:37Z'
  updated_at: '2026-04-29T02:29:18Z'
  closed_at: '2026-04-29T02:29:18Z'
parent: TASK-165
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In _run_api_worker, after focus + provider + model resolution, resolve capabilities, run git lfs pull --include=.oompah/attachments/<id>/ in the worktree, build the attachment list, and call render_prompt with attachments + capabilities. Pass the resulting RenderedPrompt into ApiAgentSession.run_task. Logs a one-liner with attachment count + which were sent vs elided.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
