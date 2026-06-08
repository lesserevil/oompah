---
id: TASK-469.4
title: Time-slice dispatch selection and coalesce events
status: Backlog
assignee: []
created_date: '2026-06-08 22:17'
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
