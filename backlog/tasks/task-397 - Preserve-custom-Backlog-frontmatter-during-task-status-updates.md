---
id: TASK-397
title: Preserve custom Backlog frontmatter during task status updates
status: In Progress
assignee:
  - oompah
created_date: '2026-06-01 16:07'
updated_date: '2026-06-01 19:52'
labels:
  - bug
dependencies: []
priority: high
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During stale-task cleanup on 2026-06-01, Backlog.md task edits reserialized task frontmatter and dropped historical fields such as type, parent, and beads.*. Oompah should preserve project-specific metadata when it marks Backlog tasks In Progress or Done, or add a repair/preservation layer around CLI edits. Repro: edit TASK-388/TASK-389 status via the current BacklogMdTracker path and inspect the diff.
<!-- SECTION:DESCRIPTION:END -->
