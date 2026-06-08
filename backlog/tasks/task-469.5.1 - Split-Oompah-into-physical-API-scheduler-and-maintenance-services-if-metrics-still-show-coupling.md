---
id: TASK-469.5.1
title: >-
  Split Oompah into physical API, scheduler, and maintenance services if metrics
  still show coupling
status: Backlog
assignee: []
created_date: '2026-06-08 23:02'
labels: []
dependencies: []
parent_task_id: TASK-469.5
priority: high
ordinal: 175000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to TASK-469.5. TASK-469 delivered the immediate responsiveness isolation with nonblocking issue snapshots, dedicated API execution, dispatch coalescing, bounded candidate scans, and incremental maintenance. If the new orchestrator_metrics/api_metrics still show API stalls caused by scheduler, tracker parsing, or maintenance work after deployment, design and implement a durable local service boundary: oompah-api serving cached state/issues and accepting commands, oompah-scheduler owning dispatch/reconcile/review ticks, and oompah-maintenance owning archive/worktree cleanup/repo heal. Coordinate through SQLite or another local durable queue/cache before considering Redis.
<!-- SECTION:DESCRIPTION:END -->
