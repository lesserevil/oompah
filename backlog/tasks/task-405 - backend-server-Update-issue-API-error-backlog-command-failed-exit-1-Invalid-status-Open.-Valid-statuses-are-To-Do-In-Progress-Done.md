---
id: TASK-405
title: >-
  [backend:server] Update issue API error: backlog command failed (exit 1):
  Invalid status: Open. Valid statuses are: To Do, In Progress, Done
status: Done
assignee:
  - oompah
created_date: '2026-06-01 20:31'
updated_date: '2026-06-01 23:19'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 27000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Update issue API error: backlog command failed (exit 1): Invalid status: Open. Valid statuses are: To Do, In Progress, Done
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Started fixing the invalid Open status error by extending Backlog compatibility startup/project checks to normalize active task statuses against the project's Backlog config. The repair uses the Backlog CLI first and only falls back to direct frontmatter edits when the CLI cannot repair the task.
<!-- SECTION:NOTES:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-01 23:19

Resuming after verifying the updated global Backlog CLI supports task comments. The code fix remains the startup/project compatibility migration plus dashboard Backlog lane visibility under In-flight only.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed the invalid Open status failure by extending Backlog compatibility checks to normalize active task statuses against the project's configured status list. Invalid active statuses now move to Backlog at startup/project sync, using the Backlog CLI first and falling back to direct frontmatter repair only if the CLI cannot update the task. Also kept the Backlog dashboard column visible when In-flight only is enabled. Verified with make test: 3680 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
