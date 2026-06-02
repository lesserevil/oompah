---
id: TASK-412
title: Hide Archived column under in-flight-only dashboard filter
status: Done
assignee:
  - oompah
created_date: '2026-06-02 02:31'
updated_date: '2026-06-02 02:33'
labels:
  - bug
dependencies: []
priority: medium
ordinal: 44000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
When the dashboard in-flight-only toggle is checked, the Archived column should not render at all. This must be true even if archived tasks are present in the API payload or belong to an otherwise visible in-flight tree. The change is UI-only and must not alter task status, dispatchability, Backlog data, or the raw /api/v1/issues response.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Changed dashboard column visibility so Archived is suppressed whenever the in-flight-only toggle is on, even if archived tasks are present in the rendered data. Added focused dashboard column coverage. Verified with uv run pytest tests/test_dashboard_conditional_columns.py -q and make test (3686 passed, 18 warnings).
<!-- SECTION:FINAL_SUMMARY:END -->
