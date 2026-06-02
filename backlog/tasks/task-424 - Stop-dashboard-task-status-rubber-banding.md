---
id: TASK-424
title: Stop dashboard task status rubber-banding
status: Done
assignee:
  - oompah
created_date: '2026-06-02 21:13'
updated_date: '2026-06-02 21:26'
labels: []
dependencies: []
priority: high
ordinal: 57000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Fix the dashboard bug where dragging or moving a task from one state to another appears to succeed briefly, then the UI refresh path moves the task back to its old column. Reproduce by moving a Backlog.md task between dashboard columns, identify whether the stale state comes from API cache, websocket broadcast, tracker status reconciliation, or client-side optimistic state handling, and add regression tests so a successful task status update cannot be overwritten by stale issue data.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Standardized dashboard issue grouping on canonical Backlog status strings, normalized incoming board payloads, and made drag/drop updates await PATCH results so failed moves refresh instead of silently bouncing. Added regression coverage for canonical column keys, optimistic dispatch, hide-merged filtering, draft epic columns, and drag/drop update persistence. Verified with focused dashboard tests and full make test.
<!-- SECTION:FINAL_SUMMARY:END -->
