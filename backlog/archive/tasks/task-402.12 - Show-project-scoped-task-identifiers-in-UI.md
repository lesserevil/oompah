---
id: TASK-402.12
title: Show project-scoped task identifiers in UI
status: Done
assignee: []
created_date: '2026-06-01 19:48'
updated_date: '2026-06-01 22:40'
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
Completed as part of the Backlog-only tracker migration. Removed Beads/bd runtime paths where applicable, moved lifecycle behavior to canonical Backlog.md statuses, updated UI/API/tests/docs for Backlog-only behavior, and verified with make test: 3677 passed.
<!-- SECTION:FINAL_SUMMARY:END -->
