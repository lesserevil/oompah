---
id: TASK-465.6
title: Preserve Backlog priority when updating task status
status: Open
assignee: []
created_date: '2026-06-08 19:52'
updated_date: '2026-06-08 19:52'
labels:
  - bug
dependencies: []
parent_task_id: TASK-465
priority: high
ordinal: 167000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During live recovery on 2026-06-08, TASK-465.3 lost its priority: 0 field after a status-only recovery/update path marked it Open for re-dispatch. Priority loss changes scheduler behavior because P0 tasks bypass some gates and are sorted first.

Audit BacklogMdTracker.update_issue and any CLI/direct-frontmatter update path used by dispatch, restart recovery, orphan reset, and handoff-label cleanup. Status-only or comment-only updates must preserve existing priority metadata exactly unless the caller explicitly changes priority.

Acceptance criteria:
- Updating only status preserves an existing priority: 0 field.
- Restart recovery preserves priority on undrained tasks.
- Regression tests cover status updates and restart recovery for P0 tasks.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 19:52
---
Filed from live recovery: TASK-465.3 lost priority: 0 after status-only restart recovery, which can affect scheduler priority and gate bypass behavior.
---
<!-- COMMENTS:END -->
