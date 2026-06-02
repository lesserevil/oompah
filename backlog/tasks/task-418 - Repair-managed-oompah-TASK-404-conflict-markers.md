---
id: TASK-418
title: Repair managed oompah TASK-404 conflict markers
status: Backlog
assignee: []
created_date: '2026-06-02 14:15'
labels:
  - bug
dependencies: []
priority: high
ordinal: 50000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The running oompah service logs repeated warnings while reading the managed oompah repository: /home/shedwards/.oompah/repos/oompah/backlog/tasks/task-404 - Show-dashboard-warning-when-agent-retries-fail-from-missing-credentials.md contains Git conflict markers in YAML frontmatter (<<<<<<< Updated upstream / ======= / >>>>>>> Stashed changes). Because the frontmatter cannot be parsed, BacklogMdTracker skips TASK-404 and the dashboard/API cannot show that task correctly from the managed repo. Fix by resolving the conflict markers in the managed repo task file to the intended canonical metadata, preserving the existing comments/body, and verifying the service log no longer reports Cannot parse task metadata for TASK-404 after restart or board refresh.
<!-- SECTION:DESCRIPTION:END -->
