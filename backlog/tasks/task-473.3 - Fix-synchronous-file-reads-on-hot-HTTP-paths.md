---
id: TASK-473.3
title: Fix synchronous file reads on hot HTTP paths
status: Backlog
assignee: []
created_date: '2026-06-09 04:19'
labels:
  - 'needs:backend'
  - performance
dependencies: []
parent_task_id: TASK-473
priority: low
ordinal: 201000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Found during benchmarking: the favicon route does fav.read_bytes() per request inside an async handler (templates are already cached, favicon is not). Cache or async-serve such static reads on hot paths.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Favicon and similar hot-path static assets are not re-read from disk per request on the event loop
<!-- AC:END -->
