---
id: TASK-179
title: Auto-commit generated attachments on agent completion
status: Done
assignee: []
created_date: 2026-04-28 20:57
updated_date: 2026-04-29 02:35
labels:
- beads-migrated
dependencies:
- TASK-178
priority: medium
ordinal: 1000
type: task
beads:
  id: oompah-e6y.3
  state: closed
  parent_id: oompah-e6y
  dependencies:
  - oompah-e6y.2
  branch_name: oompah-e6y.3
  target_branch: null
  url: null
  created_at: '2026-04-28T20:57:23Z'
  updated_at: '2026-04-29T02:35:37Z'
  closed_at: '2026-04-29T02:35:37Z'
parent: TASK-164
---
## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
On successful agent run, the orchestrator stages anything new under .oompah/attachments/<issue>/outputs/ and includes those paths in the agent's commit. Over-cap outputs are dropped before staging with a warning comment on the issue. Tests cover the commit content and the over-cap drop path.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENTS:END -->
