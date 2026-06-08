---
id: TASK-469.4
title: Time-slice dispatch selection and coalesce events
status: Done
assignee:
  - oompah
created_date: '2026-06-08 22:17'
updated_date: '2026-06-08 23:02'
labels: []
dependencies: []
parent_task_id: TASK-469
priority: high
ordinal: 173000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The 2026-06-08 slow tick spent 231268ms in dispatch handling. The event loop currently runs a full world scan for startup, full sync, worker exit, refresh, and retry events. Add event coalescing and targeted handlers so worker exits/retries do not always trigger full dispatch scans. Time-slice selection to only examine enough candidates to fill available slots plus a small buffer, and defer the rest to later ticks.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added dispatch event coalescing and bounded dispatch/duplicate-detection selection so each tick examines only enough work to fill available slots plus a configured buffer.
<!-- SECTION:FINAL_SUMMARY:END -->
