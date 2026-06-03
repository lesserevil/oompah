---
id: TASK-439
title: Ignore malformed Backlog task ids in managed repos
status: Done
assignee:
  - oompah
created_date: '2026-06-03 20:17'
updated_date: '2026-06-03 20:23'
labels: []
dependencies: []
priority: high
ordinal: 75000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When Backlog task frontmatter is corrupted, for example id: TASK-TASK- with an empty title, Oompah trusts that id and the dashboard can show project-prefixed labels such as trickle-TASK-. Fall back to the filename-derived task id/title when frontmatter id is not a valid Backlog numeric task id.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added malformed Backlog task-id fallback so corrupted frontmatter such as id: TASK-TASK- resolves through the numeric task id and title from the task filename. Tightened dashboard display formatting so only numeric TASK ids are project-shortened, preventing labels like trickle-TASK-.
<!-- SECTION:FINAL_SUMMARY:END -->
