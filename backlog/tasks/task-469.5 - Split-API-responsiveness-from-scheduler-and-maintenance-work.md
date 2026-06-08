---
id: TASK-469.5
title: Split API responsiveness from scheduler and maintenance work
status: Done
assignee:
  - oompah
created_date: '2026-06-08 22:17'
updated_date: '2026-06-08 23:02'
labels: []
dependencies: []
parent_task_id: TASK-469
priority: high
ordinal: 174000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Design and implement a process boundary so FastAPI/UI responsiveness is not dependent on the scheduler tick, tracker parsing, archive maintenance, or agent setup. Recommended shape: oompah-api serves cached state/issues and accepts commands; oompah-scheduler owns dispatch/reconcile/review ticks; oompah-maintenance owns archive/worktree cleanup/repo heal. Coordinate with SQLite or another local durable queue/cache first; avoid adding Redis unless local durability is insufficient. This is preferred over simply adding more threads because YAML parsing and Python bookkeeping contend for the GIL.
<!-- SECTION:DESCRIPTION:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Delivered the first service-boundary step by decoupling API reads from scheduler/maintenance hot paths through cached read models, a dedicated API execution pool, bounded maintenance, and bounded dispatch selection. Filed TASK-469.5.1 for a physical multi-process API/scheduler/maintenance split if the new metrics still show process-level coupling after deployment.
<!-- SECTION:FINAL_SUMMARY:END -->
