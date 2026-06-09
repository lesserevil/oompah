---
id: TASK-472.1
title: Add granian dependency and run target
status: Backlog
assignee: []
created_date: '2026-06-09 04:19'
labels:
  - 'needs:backend'
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 190000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add granian to pyproject.toml dependencies and refresh uv.lock. Add a make target (e.g. 'make run-granian') and/or document the invocation. Currently granian is only installed ad hoc in the venv.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 granian pinned in pyproject.toml and present in uv.lock
- [ ] #2 Documented/Make target to launch with --server granian
<!-- AC:END -->
