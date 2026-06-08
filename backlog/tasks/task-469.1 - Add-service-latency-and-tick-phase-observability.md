---
id: TASK-469.1
title: Add service latency and tick phase observability
status: Done
assignee:
  - oompah
created_date: '2026-06-08 22:17'
updated_date: '2026-06-08 23:02'
labels: []
dependencies: []
parent_task_id: TASK-469
priority: high
ordinal: 170000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add durable observability for Oompah responsiveness: endpoint latency histograms for /api/v1/state and /api/v1/issues, per-tick subphase timings below the current dispatch aggregate, candidate counts, per-project tracker parse counts/timing, thread-pool queue depth or active worker counts, and currently-running maintenance jobs. The goal is to make hangs diagnosable from the UI/logs without manual shell sampling.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added API latency metrics for /api/v1/state and /api/v1/issues, tick and dispatch phase timings, thread-pool queue depth, tracker read stats, and maintenance status in the state snapshot.
<!-- SECTION:FINAL_SUMMARY:END -->
