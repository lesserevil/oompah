---
id: TASK-454.1
title: Read target branch and release-pick metadata from Backlog tasks
status: Backlog
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 17:30'
labels:
  - task
dependencies: []
parent_task_id: TASK-454
priority: high
ordinal: 91000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
BacklogMdTracker should populate Issue.target_branch from oompah.target_branch or compatible frontmatter, and expose parsed oompah.backports / oompah.backport_of metadata through existing metadata helpers. Include tests for missing, scalar, and nested metadata.
<!-- SECTION:DESCRIPTION:END -->
