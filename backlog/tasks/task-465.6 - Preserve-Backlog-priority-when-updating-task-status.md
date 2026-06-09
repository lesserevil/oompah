---
id: TASK-465.6
title: Preserve Backlog priority when updating task status
status: In Progress
assignee: []
created_date: '2026-06-08 19:52'
updated_date: '2026-06-09 03:13'
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
created: 2026-06-08 20:47
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:47
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 21:00
---
Agent completed successfully in 798s (24101 tokens)
---

author: oompah
created: 2026-06-08 21:00
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 96, Tool calls: 55
- Tokens: 51 in / 24.1K out [24.1K total]
- Cost: $0.0000
- Exit: normal, Duration: 13m 18s
- Log: TASK-465.6__20260608T204807Z.jsonl
---

author: oompah
created: 2026-06-09 00:04
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 00:04
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-09 00:07
---
Agent completed successfully in 185s (4170 tokens)
---

author: oompah
created: 2026-06-09 00:07
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 38, Tool calls: 18
- Tokens: 16 in / 4.2K out [4.2K total]
- Cost: $0.0000
- Exit: normal, Duration: 3m 5s
- Log: TASK-465.6__20260609T000456Z.jsonl
---

author: oompah
created: 2026-06-09 03:08
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 03:13
---
Understanding: This issue is NOT a duplicate of TASK-425. TASK-425 fixed the general P0 priority read/write round-trip (mapping 0 vs 'high'). TASK-465.6 is distinct: the Backlog CLI silently drops numeric frontmatter priority (like 'priority: 0') during any edit — even status-only edits — because it only accepts named strings (high/medium/low). A prior agent (run #1) already implemented the fix: _custom_frontmatter_snapshot() now includes numeric int priorities in its snapshot, so _restore_missing_frontmatter() can restore them after the CLI rewrites the file. Implementation and regression tests are committed in commit f9fb998.
---
<!-- COMMENTS:END -->
