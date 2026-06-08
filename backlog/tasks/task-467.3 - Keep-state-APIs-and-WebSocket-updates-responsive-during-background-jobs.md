---
id: TASK-467.3
title: Keep state APIs and WebSocket updates responsive during background jobs
status: Open
assignee: []
created_date: '2026-06-08 18:48'
labels:
  - task
  - tick-latency
  - responsiveness
  - 'needs:backend'
  - 'needs:frontend'
  - 'needs:test'
dependencies:
  - TASK-466.4
  - TASK-467.2
references:
  - oompah/server.py
  - oompah/orchestrator.py
modified_files:
  - oompah/server.py
  - oompah/orchestrator.py
  - tests/test_server_issue_detail.py
  - tests/test_dashboard_running_agent_project_filter.py
parent_task_id: TASK-467
priority: 0
ordinal: 13
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure /api/v1/state, dashboard WebSocket state broadcasts, and status rendering use cached snapshots or lock-free reads instead of waiting behind long maintenance jobs. Avoid exposing tokens or secret project fields when surfacing maintenance and timing diagnostics.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 State API calls return promptly while maintenance is running.
- [ ] #2 WebSocket state broadcasts continue to reflect running agents and maintenance status.
- [ ] #3 Diagnostics included in API responses are secret-safe.
<!-- AC:END -->
