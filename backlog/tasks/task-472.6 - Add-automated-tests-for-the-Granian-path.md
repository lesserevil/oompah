---
id: TASK-472.6
title: Add automated tests for the Granian path
status: Backlog
assignee: []
created_date: '2026-06-09 04:19'
labels:
  - 'needs:test'
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 195000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Promote the throwaway e2e harness (boot under --server granian, HTTP route, /api/v1/state, WS initial push, orchestrator->_broadcast->WS client, restart) into tests/. The 36 existing ASGI TestClient tests only cover the uvicorn/no-op path. Mark/skip cleanly if granian is not installed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 tests/ contains a granian e2e test covering HTTP + WS broadcast + restart
- [ ] #2 Test is hermetic (temp backlog project, free port) and CI-runnable
<!-- AC:END -->
