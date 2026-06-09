---
id: TASK-406
title: Fix Backlog status config serialization for oompah statuses
status: Done
assignee:
  - oompah
created_date: '2026-06-01 21:36'
updated_date: '2026-06-01 23:51'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 29000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The Backlog CLI accepts custom statuses only when the statuses config is serialized as an inline YAML array. oompah/backlog_compat.py currently writes statuses as a block list via PyYAML safe_dump, so backlog config list falls back to To Do/In Progress/Done and dashboard moves to Open fail. Update the compatibility writer and tests so canonical statuses are emitted in Backlog-compatible inline form.
<!-- SECTION:DESCRIPTION:END -->

## Comments
<!-- COMMENTS:BEGIN -->
<!-- COMMENT:BEGIN -->
index: 1
author: oompah
created: 2026-06-01 23:47

Investigated failed move of oompah-389 to Open. The task stayed in Backlog because Backlog CLI ignored the block-list statuses written by oompah and validated against To Do/In Progress/Done.
<!-- COMMENT:END -->
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed Backlog compatibility serialization so canonical oompah statuses are written as an inline YAML array that Backlog CLI 1.45.2 validates. Added regression coverage for block-list-to-inline rewrites and updated current-config fixtures. Verification: make test passed with 3681 passed, 17 warnings.
<!-- SECTION:FINAL_SUMMARY:END -->
