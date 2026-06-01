---
id: TASK-402.12
title: Show project-scoped task identifiers in UI
status: Done
assignee: []
created_date: '2026-06-01 19:48'
updated_date: '2026-06-01 20:00'
labels: []
dependencies: []
parent_task_id: TASK-402
priority: medium
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Cosmetic UI-only change: wherever the dashboard displays a Backlog task identifier like TASK-1234, render it as ProjectName-1234 using the owning project's display name. Do not change the real task identifier used for API calls, URLs, drag/drop, or tracker operations. Add regression tests for API/frontend display data and card rendering.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added project-scoped display identifiers for Backlog task ids in dashboard payloads and visible UI labels while preserving raw identifiers for actions, API calls, drag/drop, and mutations. Added regression coverage for REST, WebSocket, detail payloads, and dashboard template usage.
<!-- SECTION:FINAL_SUMMARY:END -->
