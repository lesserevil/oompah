---
id: TASK-400
title: Prevent dashboard task moves from rubber-banding
status: Done
assignee:
  - oompah
created_date: '2026-06-01 16:16'
updated_date: '2026-06-01 16:18'
labels:
  - bug
dependencies: []
priority: high
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fix the dashboard optimistic update race where stale websocket issue payloads can move a card back to its old column after a local status change, then later snap forward again.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Dashboard optimistic updates now remain active across stale websocket issue payloads and clear only after the raw server payload confirms the requested state or priority.
<!-- SECTION:FINAL_SUMMARY:END -->
