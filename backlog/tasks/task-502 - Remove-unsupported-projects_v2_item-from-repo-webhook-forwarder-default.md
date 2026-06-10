---
id: TASK-502
title: Remove unsupported projects_v2_item from repo webhook forwarder default
status: Done
assignee: []
created_date: '2026-06-10 02:42'
updated_date: '2026-06-10 02:43'
labels:
  - bug
dependencies: []
priority: high
ordinal: 220000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The GitHub webhook forwarder added projects_v2_item to the repo-scoped gh webhook forward event list, but gh rejects that event for repository hooks. The forwarder exits at startup, leaving GitHub webhook forwarding unavailable. Remove the unsupported event from the default repo-scoped forwarder configuration while keeping parser support and documentation for externally delivered project events.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-10 02:42
---
Fixing the repo-scoped webhook default after PR #262 made gh webhook forward exit with 'projects_v2_item not allowed'.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Removed unsupported projects_v2_item from the repo-scoped gh webhook forward default, updated docs/env example, and kept parser/server support for externally delivered project item webhooks.
<!-- SECTION:FINAL_SUMMARY:END -->
