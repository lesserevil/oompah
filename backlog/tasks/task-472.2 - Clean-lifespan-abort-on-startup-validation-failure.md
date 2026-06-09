---
id: TASK-472.2
title: Clean lifespan abort on startup-validation failure
status: Backlog
assignee: []
created_date: '2026-06-09 04:19'
labels:
  - 'needs:backend'
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 191000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
setup_services() calls sys.exit(1) on config/backlog/profile validation errors. Inside the Granian worker lifespan this surfaces as 'Task exception was never retrieved' and can trigger worker respawn loops. Replace with a clean failure that aborts the Granian supervisor (no respawn), while preserving the uvicorn path behavior.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Validation failure under granian stops the process cleanly with a clear log and non-zero exit
- [ ] #2 No 'Task exception was never retrieved'; no respawn loop
- [ ] #3 uvicorn path behavior unchanged
<!-- AC:END -->
