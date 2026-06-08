---
id: TASK-469.1
title: Add service latency and tick phase observability
status: Backlog
assignee: []
created_date: '2026-06-08 22:17'
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
