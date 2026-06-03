---
id: TASK-418
title: Repair managed oompah TASK-404 conflict markers
status: Done
assignee:
  - oompah
created_date: '2026-06-02 14:15'
updated_date: '2026-06-03 01:05'
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

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Resolved the managed oompah checkout TASK-404 frontmatter conflict, verified Backlog can parse TASK-404, preserved the dirty managed task edits in a named stash, fast-forwarded the managed checkout to origin/main, and confirmed the dashboard API now returns current oompah tasks.
<!-- SECTION:FINAL_SUMMARY:END -->
