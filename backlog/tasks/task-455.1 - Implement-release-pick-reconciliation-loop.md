---
id: TASK-455.1
title: Implement release-pick reconciliation loop
status: Backlog
assignee: []
created_date: '2026-06-08 17:29'
updated_date: '2026-06-08 17:30'
labels:
  - task
dependencies:
  - TASK-454.4
parent_task_id: TASK-455
priority: high
ordinal: 96000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add an idempotent background reconciliation pass that scans merged source tasks and epics with oompah.backports metadata, evaluates each target branch, and advances stale or pending targets without creating duplicates.
<!-- SECTION:DESCRIPTION:END -->
