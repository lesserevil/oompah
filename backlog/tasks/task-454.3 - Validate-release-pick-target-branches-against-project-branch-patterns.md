---
id: TASK-454.3
title: Validate release-pick target branches against project branch patterns
status: Backlog
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 17:30'
labels:
  - task
dependencies:
  - TASK-454.1
parent_task_id: TASK-454
priority: high
ordinal: 93000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add validation that requested release-pick targets match the managed project's configured branch patterns and are not protected source-only branches unless explicitly allowed. Return actionable errors for unknown or untracked targets.
<!-- SECTION:DESCRIPTION:END -->
